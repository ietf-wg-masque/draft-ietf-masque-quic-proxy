---
title: Proxying QUIC using HTTP/3
abbrev: QUIC Proxying
docname: draft-pauly-connect-quic-latest
category: exp

ipr: trust200902
keyword: Internet-Draft

stand_alone: yes
pi: [toc, sortrefs, symrefs]

author:
 -
    ins: T. Pauly
    name: Tommy Pauly
    org: Apple Inc.
    street: One Apple Park Way
    city: Cupertino, California 95014
    country: United States of America
    email: tpauly@apple.com

--- abstract

This document defines a technique for proxying QUIC connections using an HTTP/3 proxy.

--- middle

# Introduction {#introduction}

This document defines a technique for proxying QUIC connections {{!I-D.ietf-quic-transport}}
using an HTTP/3 {{!I-D.ietf-quic-http}} proxy.

Specifically, this document defines the CONNECT-QUIC HTTP method to support QUIC
as a proxied protocol.

This document uses the term "target" to refer to the server that a client is accessing via a proxy.
This target may be an origin hosting content, or another proxy.

This approach to proxying creates two modes for QUIC packets going through a proxy:

1. Tunnelled, in which client <-> target QUIC packets are encapsulated inside client <-> proxy QUIC packets.
These packets use multiple layers of encryption and congestion control. QUIC long header packets MUST use
this mode.

2. Forwarded, in which client <-> target QUIC packets are sent directly over the client <-> UDP socket.
These packets are only encrypted using the client-target keys, and use the client-target congestion control.
This mode can only be used for QUIC short header packets.

Forwarding is defined as an optimization to reduce CPU processing on clients and proxies, as well as overhead
for packets on the wire. It provides equivalent properties to cleartext TCP proxies, in that targets see the proxy's
IP address instead of the client's IP address, but packets sent client <-> proxy and proxy <-> target are easily
correlatable to entities who can observe traffic on both sides of the proxy.

## Conventions and Definitions {#conventions}

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD",
"SHOULD NOT", "RECOMMENDED", "NOT RECOMMENDED", "MAY", and "OPTIONAL" in this
document are to be interpreted as described in BCP 14 {{!RFC2119}} {{!RFC8174}}
when, and only when, they appear in all capitals, as shown here.

# Proxying using QUIC Connection IDs

The method described in this document proxies flows at the granularity of QUIC
Connection IDs, which are exposed in QUIC packets and can be used for
identifying and routing the packets. Each QUIC Connection ID represents one direction
of QUIC packets, with the Connection ID being owned and defined by the receiver of the packets.

A Connection ID that is defined by the client of HTTP/3 proxy, and is used
to route packets from the target server to the client when it is a Destination Connection ID,
is referred to as the "Client Connection ID".

A Connection ID that is defined by the target server accessed via an HTTP/3 proxy, and is used
to route packets from the client to the target server when it is a Destination Connection ID,
is referred to as the "Server Connection ID".

QUIC packets can be either tunnelled within an HTTP/3 proxy connection using
QUIC DATAGRAM frames, or be forwarded directly alongside an HTTP/3 proxy
connection on the same set of IP addresses and UDP ports. CONNECT-QUIC allows
clients to specify either form of transport.

# The CONNECT-QUIC Method {#connect-quic-method}

The CONNECT-QUIC method establishes a proxy forwarding path for
a particular flow of datagrams associated with a QUIC Connection ID.

CONNECT-QUIC requests follow the same header requirements as CONNECT requests,
as defined in Section 8.3 of {{!RFC7540}}. Notably, the request MUST include the :authority
pseudo-header field containing the host and port to which to connect.

Body payloads within CONNECT-QUIC requests are undefined, and SHOULD be treated
as malformed.

CONNECT-QUIC responses are not cacheable.

The CONNECT-QUIC method as defined in this document can only be supported
by an HTTP/3 proxy. Use of CONNECT-QUIC with older HTTP versions is undefined and
MUST be rejected.

[[OPEN ISSUE: Some clients might be unable to connect to proxies with HTTP/3, so HTTP/2 support may be needed.]]

## CONNECT-QUIC Headers

CONNECT-QUIC requests and responses include headers that describe how the proxy routes
QUIC packets matching a given Connection ID.

The "Client-Connection-Id" header is a Byte Sequence Structured Field {{!I-D.ietf-httpbis-header-structure}}
containing a client's QUIC Connection ID. The byte sequence MAY be zero-length. The ABNF is:

~~~
   Client-Connection-Id = sf-binary
~~~

The "Server-Connection-Id" header is a Byte Sequence Structured Field {{!I-D.ietf-httpbis-header-structure}}
containing a target server's QUIC Connection ID. The byte sequence MAY be zero-length. The ABNF is:

~~~
   Server-Connection-Id = sf-binary
~~~

The "Datagram-Flow-ID" header is an Integer Structured Field {{!I-D.ietf-httpbis-header-structure}}
containing the QUIC datagram flow ID to use for tunnelling packets {{!I-D.schinazi-quic-h3-datagram}}
{{!I-D.ietf-quic-datagram}}. The ABNF is:

~~~
  Datagram-Flow-Id = sf-integer
~~~

## Client Request Behavior

Whenever a client wants to send QUIC packets through the proxy, or receive
QUIC packets via the proxy, it sends a new CONNECT-QUIC request.

Clients can choose to send QUIC packets to the proxy either tunnelled within
DATAGRAM frames, or sent directly to the proxy's IP address and port.

Each request MUST contain exactly one connection ID header, either Client-Connection-Id
or Server-Connection-Id. Client-Connection-Id requests define paths for receiving
packets from the target server to the client, and Server-Connection-Id requests define paths
for sending packets from the client to target server.

Packets tunnelled within DATAGRAM frames can be sent as soon as the
CONNECT-QUIC request has been sent, even in the same QUIC packet to the proxy.
That is, the QUIC packet sent from the client to the proxy can contain a STREAM
frame with the CONNECT-QUIC request, as well as a DATAGRAM frame that contains
a tunnelled QUIC packet to forward. This is particularly useful for reducing round trips.
Note that packets sent in DATAGRAM frames before the proxy has sent its
CONNECT-QUIC response might be dropped if the proxy rejects the request.
Any DATAGRAM frames that are sent in a separate QUIC packet from the STREAM
frame that contains the CONNECT-QUIC request might also be dropped in
the case that the packet arrives at the proxy before the packet containing the
STREAM frame.

Packets forwarded by sending directly to the proxy's IP address and port MUST
wait for a successful response to the CONNECT-QUIC request. This ensures
that the proxy knows how to forward a given packet.

Clients sending QUIC Long Header packets MUST tunnel them within DATAGRAM
frames to avoid exposing unnecessary connection metadata. QUIC Short Header
packets, on the other hand, can send directly to the proxy (without any tunnelling
or encapsulation) once the proxy has sent a successful response for the Server Connection ID.

Clients SHOULD establish mappings for any Client Connection ID values it provides to
the destination target. Failure to do so will prevent the target from initiating
connection migration probes along new paths.

## Proxy Response Behavior

Upon receipt of a CONNECT-QUIC request, the proxy attempts to establish a forwarding
path, and validates that it has no overlapping mappings. This includes:

- Validating that the request include one of either the Client-Connection-Id and
the Server-Connection-Id header, along with a Datagram-Flow-Id header. Requests absent
any connection ID header MUST be rejected.
- Creating a mapping entry for the QUIC Connection ID in the given direction (client or target server)
associated with the client's IP address and UDP port.
For any non-zero-length Client Connection ID, the Connection ID MUST be unique
across all other clients.
- Allocating a UDP socket on which to communicate with the requested target server.

If these operations can be completed the proxy sends a 2xx (Successful) response.
This response MUST also echo any Client-Connection-Id, Server-Connection-Id, and
Datagram-Flow-Id headers included in the request.

At this point, any DATAGRAM frames sent by the client matching a known Server
Connection ID will be forwarded on the correct UDP socket. Specifically, the proxy
extracts the contents of each DATAGRAM frame and writes them to the UDP socket
created in response to the CONNECT-QUIC request. Any packets received directly
to the proxy from the client that match a known Server Connection ID will be
forwarded similarly.

Any packets received by the proxy from a target server that match a known Client Connection
ID on a matching UDP socket need to be forwarded to the client. The proxy MUST
use DATAGRAM frames on the associated flow ID for any Long Header packets. The proxy
SHOULD forward directly to the client for any matching Short Header packets.

## Connection ID Mapping Lifetime

Each CONNECT-QUIC request consumes one bidirectional HTTP/3 stream. For any stream
on which the proxy has sent a response indicating success, the mapping for forwarding a
Connection ID lasts as long as the stream is open.

A client that no longer wants a given Connection ID to be forwarded by the proxy, for either
direction, MUST reset the stream.

# Example

Consider a client that is establishing a new QUIC connection through the proxy.
It has selected a Client Connection ID of 0x31323334. It selects the next open datagram flow ID (1).
In order to inform a proxy of the new QUIC Client Connection ID, and bind that connection ID
to datagram flow 1, the client sends the following CONNECT-QUIC request:

~~~
HEADERS + END_HEADERS
:method = CONNECT-QUIC
:authority = target.example.com:443
client-connection-id = :MTIzNA==:
datagram-flow-id = 1
~~~

The client will also send the initial QUIC packet with the Long Header form in a DATAGRAM frame
with flow ID 1.

Once the proxy sends a 200 response indicating success, packets received by the proxy
that match the Connection ID 0x31323334 will be directly forwarded to the client.
The proxy will also forward the initial QUIC packet received on DATAGRAM flow 1 to
target.example.com:443.

When the proxy receives a response from target.example.com:443 that has 0x31323334
as the Destination Connection ID, the proxy will forward that packet to the client on
DATAGRAM flow 1.

Once the client learns which Connection ID has been selected by the target server, it can send
a new request to the proxy to establish a mapping. In this case, that ID is 0x61626364.
The client sends the following request:

~~~
HEADERS + END_HEADERS
:method = CONNECT-QUIC
:authority = target.example.com:443
server-connection-id = :YWJjZA==:
datagram-flow-id = 1
~~~

The client also sends its reply to the target server in a DATAGRAM frame on flow 1 after sending the new
request.

Once the proxy sends a 200 response indicating success, packets sent by the client
that match the Connection ID 0x61626364 will be forwarded to the target server, i.e.,
without proxy decryption.

Upon receiving the response, the client starts sending Short Header packets with a
Destination Connection ID of 0x61626364 directly to the proxy (not tunnelled), and
these are forwarded directly to the target by the proxy. Similarly, Short Header packets
from the target with a Destination Connection ID of 0x31323334 are forwarded directly
to the client.

# Interactions with Load Balancers

Some QUIC servers are accessed using load balancers, as described in {{?I-D.ietf-quic-load-balancers}}.
These load balancers route packets to servers based on the server's Connection ID. These
Connection IDs are generated in a way that can be coordinated between servers and their load
balancers.

If a proxy that supports CONNECT-QUIC is itself running behind a load balancer, extra
complexity arises once clients start sending packets to the proxy that have Destination Connection
IDs that belong to the end servers, not the proxy. If the load balancer is not aware of these Connection
IDs, or the Connection IDs overlap with other Connection IDs used by the load balancer, packets
can be routed incorrectly.

CONNECT-QUIC proxies generally SHOULD NOT be run behind load balancers; and if they are,
they MUST coordinate between the proxy and the load balancer to create mappings for proxied
Connection IDs prior to the proxy sending 2xx (Successful) responses to clients.

# Security Considerations {#security}

Proxies that support CONNECT-QUIC SHOULD provide protections to rate-limit
or restrict clients from opening an excessive number of proxied connections, so as
to limit abuse or use of proxies to launch Denial-of-Service attacks.

Sending QUIC packets by forwarding through a proxy without tunnelling exposes
some QUIC header metadata to onlookers, and can be used to correlate packets
flows if an attacker is able to see traffic on both sides of the proxy.
Tunnelled packets have similar inference problems. An attacker on both sides
of the proxy can use the size of ingress and egress packets to correlate packets
belonging to the same connection. (Absent client-side padding, tunneled packets
will typically have a fixed amount of overhead that is removed before their
DATAGRAM contents are written to the target.)

Since proxies that forward QUIC packets do not perform any cryptographic
integrity check, it is possible that these packets are either malformed, replays, or
otherwise malicious. This may result in proxy targets rate limiting or decreasing
the reputation of a given proxy.

[[OPEN ISSUE: figure out how clients and proxies interact to learn whether an
adversary is injecting malicious forwarded packets to induce rate limiting]]

# IANA Considerations {#iana}

## HTTP Method {#iana-method}

This document registers "CONNECT-QUIC" in the HTTP Method Registry
<[](https://www.iana.org/assignments/http-methods)>.

~~~
  +--------------+------+------------+---------------+
  | Method Name  | Safe | Idempotent |   Reference   |
  +--------------+------+------------+---------------+
  | CONNECT-QUIC |  no  |     no     | This document |
  +--------------+------+------------+---------------+
~~~

## HTTP Headers {#iana-header}

This document registers the "Client-Connection-Id", "Server-Connection-Id", and
"Datagram-Flow-Id" headers in the "Permanent Message Header Field Names"
<[](https://www.iana.org/assignments/message-headers)>.

~~~
  +----------------------+----------+--------+--------------------------------------+
  | Header Field Name    | Protocol | Status |              Reference               |
  +----------------------+----------+--------+--------------------------------------+
  | Client-Connection-Id |   http   |  exp   |            This document             |
  +----------------------+----------+--------+--------------------------------------+
  | Server-Connection-Id |   http   |  exp   |            This document             |
  +----------------------+----------+--------+--------------------------------------+
  | Datagram-Flow-Id     |   http   |  exp   | {{!I-D.schinazi-masque-connect-udp}} |
  +----------------------+----------+--------+--------------------------------------+
~~~

--- back

# Acknowledgments {#acknowledgments}
{:numbered="false"}

This work-in-progress proposal is partly based on {{?I-D.schinazi-masque-connect-udp}},
and the proposal for the MASQUE protocol more generally.

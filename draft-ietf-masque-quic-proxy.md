---
title: QUIC-Aware Proxying Using HTTP
abbrev: QUIC Proxy
category: exp
docname: draft-ietf-masque-quic-proxy-latest
submissiontype: IETF
number:
date:
consensus: true
v: 3
area: Transport
wg: MASQUE
venue:
  group: "MASQUE"
  type: "Working Group"
  mail: "masque@ietf.org"
  arch: "https://mailarchive.ietf.org/arch/browse/masque/"
  github: "ietf-wg-masque/draft-ietf-masque-quic-proxy"
  latest: "https://ietf-wg-masque.github.io/draft-ietf-masque-quic-proxy/draft-ietf-masque-quic-proxy.html"
keyword:
  - quic
  - http
  - datagram
  - udp
  - proxy
  - tunnels
  - quic in quic
  - turtles all the way down
  - masque
  - http-ng

author:
 -
    ins: T. Pauly
    name: Tommy Pauly
    org: Apple Inc.
    street: One Apple Park Way
    city: Cupertino, California 95014
    country: United States of America
    email: tpauly@apple.com

 -
    ins: E. Rosenberg
    name: Eric Rosenberg
    org: Apple Inc.
    street: One Apple Park Way
    city: Cupertino, California 95014
    country: United States of America
    email: eric_rosenberg@apple.com

 -
    ins: "D. Schinazi"
    name: "David Schinazi"
    organization: "Google LLC"
    street: "1600 Amphitheatre Parkway"
    city: "Mountain View, California 94043"
    country: "United States of America"
    email: dschinazi.ietf@gmail.com

normative:
    SP800-38A:
        author:
            name: Morris Dworkin
        org: National Institute of Standards and Technology
        title: >
            Recommendation for Block Cipher Modes of Operation: Methods and Techniques
        date: 2001-12-01
        target: https://nvlpubs.nist.gov/nistpubs/legacy/sp/nistspecialpublication800-38a.pdf

--- abstract

This document defines an extension to UDP Proxying over HTTP
that adds specific optimizations for proxied QUIC connections. This extension
allows a proxy to reuse UDP 4-tuples for multiple connections. It also defines a
mode of proxying in which QUIC short header packets can be forwarded using an
HTTP/3 proxy rather than being re-encapsulated and re-encrypted.

--- middle

# Introduction {#introduction}

UDP Proxying over HTTP {{!CONNECT-UDP=RFC9298}}
defines a way to send datagrams through an HTTP proxy, where UDP is used to communicate
between the proxy and a target server. This can be used to proxy QUIC
connections {{!QUIC=RFC9000}}, since QUIC runs over UDP datagrams.

This document uses the term "target" to refer to the server that a client is
accessing via a proxy. This target may be an origin hosting content, or another
proxy.

This document extends the UDP proxying protocol to add signalling about QUIC
Connection IDs. QUIC Connection IDs are used to identify QUIC connections in
scenarios where there is not a strict bidirectional mapping between one QUIC
connection and one UDP 4-tuple (pairs of IP addresses and ports). A proxy that
is aware of Connection IDs can reuse UDP 4-tuples between itself and a target
for multiple proxied QUIC connections.

Awareness of Connection IDs also allows a proxy to avoid re-encapsulation and
re-encryption of proxied QUIC packets once a connection has been established.
When this functionality is present, the proxy can support two modes for handling
QUIC packets:

1. Tunnelled, in which client <-> target QUIC packets are encapsulated inside
client <-> proxy QUIC packets. These packets use multiple layers of encryption
and congestion control. QUIC long header packets MUST use this mode. QUIC short
header packets MAY use this mode. This is the default mode for UDP proxying.

2. Forwarded, in which client <-> target QUIC packets are sent separately over the
client <-> proxy UDP socket, using a special-purpose transform instead of full
QUIC encapsulation. This mode MUST only be used for QUIC short header packets.

Forwarded mode is defined as an optimization to reduce CPU and memory cost to clients and
proxies, as well as avoiding MTU overhead for packets on the wire. This makes it
suitable for deployment situations that otherwise relied on cleartext TCP
proxies, which cannot support QUIC and have inferior security and privacy
properties.

The properties provided by the forwarded mode are as follows:

- All packets sent between the client and the target traverse through the proxy
device.
- The target server cannot know the IP address of the client solely based on the
proxied packets the target receives.
- Observers of either or both of the client <-> proxy link and the proxy <->
target are not able to learn more about the client <-> target communication than
if no proxy was used.

Forwarded mode does not prevent correlation of client <-> proxy and proxy <->
target packets by an entity that can observe both links. The precise risks
depend on the negotiated transform ({{packet-transforms}}). See {{security}} for
further discussion.

Both clients and proxies can unilaterally choose to disable forwarded mode for
any client <-> target connection.

The forwarded mode of this extension is only defined for HTTP/3
{{!HTTP3=RFC9114}} and not any earlier versions of HTTP.

QUIC proxies only need to understand the Header Form bit, and the connection ID
fields from packets in client <-> target QUIC connections. Since these fields
are all in the QUIC invariants header {{!INVARIANTS=RFC8999}},
QUIC proxies can proxy all versions of QUIC.

## Conventions and Definitions {#conventions}

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD",
"SHOULD NOT", "RECOMMENDED", "NOT RECOMMENDED", "MAY", and "OPTIONAL" in this
document are to be interpreted as described in BCP 14 {{!RFC2119}} {{!RFC8174}}
when, and only when, they appear in all capitals, as shown here.

## Terminology

This document uses the following terms:

- Client: the client of all QUIC connections discussed in this document.
- Proxy: the endpoint that responds to the UDP proxying request.
- Target: the server that a client is accessing via a proxy.
- Client <-> Proxy HTTP stream: a single HTTP stream established from
the client to the proxy.
- Socket: a UDP 4-tuple (local IP address, local UDP port, remote IP address,
remote UDP port). In some implementations, this is referred to as a "connected"
socket.
- Client-facing socket: the socket used to communicate between the client and
the proxy.
- Target-facing socket: the socket used to communicate between the proxy and
the target.
- Client Connection ID: a QUIC Connection ID that is chosen by the client, and
is used in the Destination Connection ID field of packets from the target to
the client.
- Target Connection ID: a QUIC Connection ID that is chosen by the target, and
is used in the Destination Connection ID field of packets from the client to
the target.
- Virtual Client Connection ID: a fake QUIC Connection ID that is chosen by the
proxy that the proxy MUST use when sending QUIC packets in forwarded mode.
- Virtual Target Connection ID: a fake QUIC Connection ID that is chosen by the
proxy that the client MUST use when sending QUIC packets in forwarded mode.
- Packet Transform: the procedure used to modify packets before they enter the
client-proxy link.

## Virtual Connection IDs

Servers receiving QUIC packets can employ load balancing
strategies such as those described in {{?QUIC-LB=I-D.ietf-quic-load-balancers}}
that encode routing information in
the connection ID. When operating in forwarded mode, clients send QUIC packets
destined for the Target directly to the Proxy. Since these packets are generated
using the Target Connection ID, load balancers would not be able to route packets
to the correct Proxy if the packets were sent with the Target Connection ID.
The Virtual Target Connection ID is a connection ID chosen
by the Proxy that the Client uses when sending forwarded mode packets. The Proxy
replaces the Virtual Target Connection ID with the Target Connection ID prior to
forwarding the packet to the Target.

Similarly, QUIC requires that connection IDs aren't reused over multiple network
paths to avoid linkability. The Virtual Client Connection ID is a connection ID
chosen by the Proxy that the Proxy uses when sending forwarded mode packets.
The Proxy replaces the Client Connection ID with the Virtual Client Connection
ID prior to forwarding the packet to the Client. Clients take advantage of this
to avoid linkability when migrating a client to proxy network path. The Virtual
Client Connection ID allows the connection ID bytes to change on the wire
without requiring the connection IDs on the client to target connection change.
To reduce the likelihood of connection ID conflicts, the proxy SHOULD choose a
Virtual Client Connection ID that is at least as long as the Client Connection
ID. Similarly, clients multiplexing connections on the same UDP socket SHOULD
choose a Client Connection ID that's sufficiently long to reduce the likelihood
of a conflict with the proxy-chosen Virtual Client Connection ID. The Virtual
Client Connection ID MUST either be constructed such that it is unpredictable to
the client or to guarantee no conflicts among all proxies sharing an IP address
and port. See {{security}} for more discussion on Virtual Client Connection ID
construction.

Clients and Proxies not implementing forwarded mode do not need to consider
Virtual Connection IDs since all Client<->Target datagrams will be encapsulated
within the Client<->Proxy connection.

# Required Proxy State {#mappings}

In the methods defined in this document, the proxy is aware of the QUIC
Connection IDs being used by proxied connections, along with the sockets
used to communicate with the client and the target. Tracking Connection IDs in
this way allows the proxy to reuse target-facing sockets for multiple
connections and support the forwarded mode of proxying.

QUIC packets can be either tunnelled within an HTTP proxy connection using
HTTP Datagram frames {{!HTTP-DGRAM=RFC9297}}, or be forwarded
directly alongside an HTTP/3 proxy connection on the same set of IP addresses and UDP
ports. The use of forwarded mode requires the consent of both the client and the
proxy.

In order to correctly route QUIC packets in both tunnelled and forwarded modes,
the proxy needs to maintain mappings between several items. There are three
required unidirectional mappings, described below.

## Stream Mapping

Each client <-> proxy HTTP stream MUST be mapped to a single target-facing socket.

~~~
(Client <-> Proxy HTTP Stream) => Target-facing socket
~~~

Multiple streams can map to the same target-facing socket, but a
single stream cannot be mapped to multiple target-facing sockets.
Each stream MUST also be associated with a single Packet Transform.

This mapping guarantees that any HTTP Datagram using a stream sent
from the client to the proxy in tunnelled mode can be sent to the correct
target.

## Virtual Target Connection ID Mapping

Each pair of Virtual Target Connection ID and client-facing socket MUST map to a
single target-facing socket and Target Connection ID.

~~~
(Client-facing socket + Virtual Target Connection ID)
    => (Target-facing socket + Target Connection ID)
~~~

Multiple pairs of Connection IDs and client-facing sockets can map to the
same target-facing socket.

This mapping guarantees that any QUIC packet containing the Virtual Target
Connection ID sent from the client to the proxy in forwarded mode can be sent to
the correct target with the correct Target Connection ID. Thus, a proxy that
does not allow forwarded mode does not need to maintain this mapping.

## Client Connection ID Mappings

Each pair of Client Connection ID and target-facing socket MUST map to a single
stream on a single client <-> proxy HTTP stream. Additionally, when supporting
forwarded mode, the pair of Client Connection ID and target-facing socket MUST
map to a single client-facing socket and Virtual Client Connection ID.

~~~
(Target-facing socket + Client Connection ID) => (Client <-> Proxy HTTP Stream)
(Target-facing socket + Client Connection ID)
    => (Client-facing socket + Virtual Client Connection ID)
~~~

Multiple pairs of Connection IDs and target-facing sockets can map to the same
HTTP stream or client-facing socket.

These mappings guarantee that any QUIC packet sent from a target to the proxy
can be sent to the correct client, in either tunnelled or forwarded mode. Note
that this mapping becomes trivial if the proxy always opens a new target-facing
socket for every client request with a unique stream. The mapping is
critical for any case where target-facing sockets are shared or reused.

## Detecting Connection ID Conflicts {#conflicts}

In order to be able to route packets correctly in both tunnelled and forwarded
mode, proxies check for conflicts before creating a new mapping. If a conflict
is detected, the proxy will reject the client's request, as described in
{{proxy-behavior}}.

Two sockets conflict if and only if all members of the 4-tuple (local IP
address, local UDP port, remote IP address, and remote UDP port) are identical.

Two Connection IDs conflict if and only if one Connection ID is equal to or a
prefix of another. For example, a zero-length Connection ID conflicts with all
connection IDs. This definition of a conflict originates from the fact that
QUIC short headers do not carry the length of the Destination Connection ID
field, and therefore if two short headers with different Destination Connection
IDs are received on a shared socket, one being a prefix of the other prevents
the receiver from identifying which mapping this corresponds to.

The proxy treats two mappings as being in conflict when a conflict is detected
for all elements on the left side of the mapping diagrams above.

Since very short Connection IDs are more likely to lead to conflicts,
particularly zero-length Connection IDs, a proxy MAY choose to reject all
requests for very short Connection IDs as conflicts, in anticipation of future
conflicts.

## Stateless Resets for Forwarded Mode QUIC Packets

While the lifecycle of forwarding rules are bound to the lifecycle of the
client<->proxy HTTP stream, a peer may not be aware that the stream has
terminated. If the above mappings are lost or removed without the peer's
knowledge, they may send forwarded mode packets even though the Client
or Proxy no longer has state for that connection. To allow the Client or
Proxy to reset the client<->target connection in the absence of the mappings
above, a stateless reset token corresponding to the Virtual Connection ID
can be provided.

Consider a proxy that initiates closure of a client<->proxy QUIC connection.
If the client is temporarily unresponsive or unreachable, the proxy might have
considered the connection closed and removed all connection state (including
the stream mappings used for forwarding). If the client never learned about the closure, it
might send forwarded mode packets to the proxy, assuming the stream mappings
and client<->proxy connection are still intact. The proxy will receive these
forwarded mode packets, but won't have any state corresponding to the
destination connection ID in the packet. If the proxy has provided a stateless
reset token for the Virtual Target Connection ID, it can send a stateless reset
packet to quickly notify the client that the client<->target connection is
broken.

## Stateless Resets from the Target

Reuse of target-facing sockets is only possible because QUIC connection IDs
allow distinguishing packets for multiple QUIC connections received with the
same 5-tuple. One exception to this is Stateless Reset packets, in which the
connection ID is not used, but rather populated with unpredictable bits followed
by a Stateless Reset token, to make it indistinguishable from a regular packet
with a short header. In order for the proxy to correctly recognize Stateless
Reset packets, the client SHOULD share the Stateless Reset token for each
registered Target Connection ID. When the proxy receives a Stateless Reset packet,
it can send the packet to the client as a tunnelled datagram. Although Stateless Reset packets
look like short header packets, they are not technically short header packets and do not contain
negotiated connection IDs, and thus are not eligible for forwarded mode.

# Connection ID Capsule Types

Proxy awareness of QUIC Connection IDs relies on using capsules ({{HTTP-DGRAM}})
to signal the addition and removal of Client and Target Connection IDs.

Note that these capsules do not register contexts. QUIC packets are encoded
using HTTP Datagrams with the context ID set to zero as defined in
{{CONNECT-UDP}}.

The capsules used for QUIC-aware proxying allow a client to register connection
IDs with the proxy, and for the client and proxy to acknowledge or reject the
connection ID mappings.

The REGISTER_CLIENT_CID and REGISTER_TARGET_CID capsule types (see
{{iana-capsule-types}} for the capsule type values) allow a client to inform
the proxy about a new Client Connection ID or a new Target Connection ID,
respectively. These capsule types MUST only be sent by a client.

The ACK_CLIENT_CID and ACK_TARGET_CID capsule types (see {{iana-capsule-types}}
for the capsule type values) are sent by the proxy to the client to indicate
that a mapping was successfully created for a registered connection ID as well
as provide the Virtual Connection IDs that may be used in forwarded mode.
These capsule types MUST only be sent by a proxy.

The ACK_CLIENT_VCID capsule type MUST only be sent by the client and only when
forwarding mode is enabled. It is sent by the client to the proxy in response to
an ACK_CLIENT_CID capsule to indicate that the client is ready to receive
forwarded mode packets with the specified virtual connection ID. The proxy MUST
NOT send forwarded mode packets to the client prior to receiving this
acknowledgement. This capsule also contains a Stateless Reset Token the client
may respond with when receiving forwarded mode packets with the specified
virtual connection ID.

The CLOSE_CLIENT_CID and CLOSE_TARGET_CID capsule types (see
{{iana-capsule-types}} for the capsule type values) allow either a client
or a proxy to remove a mapping for a connection ID. These capsule types
MAY be sent by either a client or the proxy. If a proxy sends a
CLOSE_CLIENT_CID without having sent an ACK_CLIENT_CID, or if a proxy
sends a CLOSE_TARGET_CID without having sent an ACK_TARGET_CID,
it is rejecting a Connection ID registration. Similarly, if a client sends
CLOSE_CLIENT_CID without having sent an ACK_CLIENT_VCID capsule, the client is
either rejecting the proxy-chosen Virtual Client Connection ID or no longer
needs the connection ID registered.

REGISTER_CLIENT_CID, CLOSE_CLIENT_CID, and CLOSE_TARGET_CID capsule types are
formatted as follows:

~~~
Connection ID Capsule {
  Type (i) = 0xffe500, 0xffe505, 0xffe506
  Length (i),
  Connection ID (0..2040),
}
~~~
{: #fig-capsule-cid title="Connection ID Capsule Format"}

Connection ID:
: A connection ID being registered or closed, which is between 0 and 255 bytes in
length. The length of the connection ID is implied by the length of the
capsule. Note that in QUICv1, the length of the Connection ID is limited
to 20 bytes, but QUIC invariants allow up to 255 bytes.

The REGISTER_TARGET_CID capsule includes the target-provided connection ID
and Stateless Reset Token.

~~~
Register Target Connection ID Capsule {
  Type (i) = 0xffe501
  Length (i),
  Connection ID Length (i)
  Connection ID (0..2040),
  Stateless Reset Token Length (i),
  Stateless Reset Token (..),
}
~~~
{: #fig-capsule-register-target-cid title="Register Target Connection ID Capsule Format"}

Connection ID Length
: The length of the connection ID being registered, which is between 0 and
255. Note that in QUICv1, the length of the Connection ID is limited to 20
bytes, but QUIC invariants allow up to 255 bytes.

Connection ID
: A connection ID being registered whose length is equal to Connection ID
Length. This is the real Target Connection ID.

Stateless Reset Token Length
: The length of the target-provided Stateless Reset Token.

Stateless Reset Token
: The target-provided Stateless Reset token allowing the proxy to correctly
recognize Stateless Reset packets to be tunnelled to the client.

The ACK_TARGET_CID capsule type includes a Virtual Connection ID and Stateless
Reset Token.

~~~
Acknowledge Target Connection ID Capsule {
  Type (i) = 0xffe504
  Length (i)
  Connection ID Length (i)
  Connection ID (0..2040),
  Virtual Connection ID Length (i)
  Virtual Connection ID (0..2040),
  Stateless Reset Token Length (i),
  Stateless Reset Token (..),
}
~~~
{: #fig-capsule-ack-target-cid title="Acknowledge Target Connection ID Capsule Format"}

Connection ID Length
: The length of the connection ID being acknowledged, which
is between 0 and 255. Note that in QUICv1, the length of the Connection ID
is limited to 20 bytes, but QUIC invariants allow up to 255 bytes.

Connection ID
: A connection ID being acknowledged whose length is equal to
Connection ID Length. This is the real Target Connection ID.

Virtual Connection ID Length
: The length of the virtual target connection ID being provided. This MUST be a
valid connection ID length for the QUIC version used in the client<->proxy QUIC
connection. When forwarded mode is not negotiated, the length MUST be zero.
The Virtual Connection ID Length and Connection ID Length SHOULD be equal
when possible to avoid the need to resize packets during replacement.

Virtual Connection ID
: The proxy-chosen connection ID that the client MUST use when sending in
forwarding mode. The proxy rewrites forwarded mode packets to contain the
correct Target Connection ID prior to sending them.

Stateless Reset Token Length
: The length of the Stateless Reset Token sent by the proxy in response to
forwarded mode packets in order to reset the Client<->Target QUIC connection.
When forwarded mode is not negotiated, the length MUST be zero. Proxies choosing
not to support stateless resets MAY set the length to zero. Clients receiving a
zero-length stateless reset token MUST ignore it.

Stateless Reset Token
: A Stateless Reset Token allowing reset of the Client<->Target connection in
response to Client->Target forwarded mode packets.

The ACK_CLIENT_CID capsule type includes a Virtual Connection ID.

~~~
Acknowledge Client Connection ID Capsule {
  Type (i) = 0xffe502
  Length (i)
  Connection ID Length (i)
  Connection ID (0..2040),
  Virtual Connection ID Length (i)
  Virtual Connection ID (0..2040),
}
~~~
{: #fig-capsule-ack-client-cid title="Acknowledge Client Connection ID Capsule Format"}

Connection ID Length
: The length of the connection ID being acknowledged, which
is between 0 and 255. Note that in QUICv1, the length of the Connection ID
is limited to 20 bytes, but QUIC invariants allow up to 255 bytes.

Connection ID
: A connection ID being acknowledged whose length is equal to
Connection ID Length. This is the real Cilent Connection ID.

Virtual Connection ID Length
: The length of the virtual client connection ID being provided. This MUST be a
valid connection ID length for the QUIC version used in the client<->proxy QUIC
connection. When forwarded mode is not negotiated, the length MUST be zero.
The Virtual Connection ID Length and Connection ID Length SHOULD be equal
when possible to avoid the need to resize packets during replacement. The
Virtual Client Connection ID Length SHOULD be at least as large as the
Connection ID to reduce the likelihood of connection ID conflicts.

Virtual Connection ID
: The proxy-chosen connection ID that the proxy MUST use when sending in
forwarding mode. The proxy rewrites forwarded mode packets to contain the
correct Virtual Client Connection ID prior to sending them to the client.

The ACK_CLIENT_VCID capsule type includes a Stateless Reset Token.

~~~
Acknowledge Virtual Client Connection ID Capsule {
  Type (i) = 0xffe503
  Length (i)
  Connection ID Length (i)
  Connection ID (0..2040),
  Virtual Connection ID Length (i)
  Virtual Connection ID (0..2040),
  Stateless Reset Token Length (i),
  Stateless Reset Token (..),
}
~~~
{: #fig-capsule-ack-virtual-client-cid title="Acknowledge Virtual Client Connection ID Capsule Format"}

Connection ID Length
: The length of the connection ID being acknowledged, which
is between 0 and 255. Note that in QUICv1, the length of the Connection ID
is limited to 20 bytes, but QUIC invariants allow up to 255 bytes.

Connection ID
: A connection ID being acknowledged whose length is equal to
Connection ID Length. This is the real Cilent Connection ID.

Virtual Connection ID Length
: The length of the virtual client connection ID being acknowledged.

Virtual Connection ID
: The proxy-chosen virtual connection ID being acknowledged whose length is
equal to Virtual Connection ID Length.

Stateless Reset Token Length
: The length of the Stateless Reset Token that may be sent by the client in
response to forwarded mode packets to reset the Client<->Target connection.
Clients choosing not to support stateless resets MAY set the length to zero.
Proxies receiving a zero-length stateless reset token MUST ignore it.

Stateless Reset Token
: A Stateless Reset Token allowing reset of the Target->Client forwarding rule
in response to Target->Client forwarded mode packets.


# Client Behavior {#client-behavior}

A client initiates UDP proxying via a CONNECT request as defined
in {{CONNECT-UDP}}. Within its request, it includes the "Proxy-QUIC-Forwarding"
header to indicate whether or not the request should support forwarding.
If this header is not included, the client MUST NOT send any connection ID
capsules.

"Proxy-QUIC-Forwarding" is an Item Structured Header {{!RFC8941}}. Its
value MUST be a Boolean.

If the client wants to enable QUIC packet forwarding for this request, it sets
the value to "?1". If it doesn't want to enable forwarding, but instead only
provide information about QUIC Connection IDs for the purpose of allowing
the proxy to share a target-facing socket, it sets the value to "?0".

The client MUST add an "accept-transform" parameter whose value is an
`sf-string` containing the supported packet transforms ({{packet-transforms}})
in order of descending preference, separated by commas. If the proxy receives a
"Proxy-QUIC-Forwarding" header without the "accept-transform" parameters, it
MUST ignore the header and respond as if the client had not sent the
"Proxy-QUIC-Forwarding" header.

If the proxy supports QUIC-aware proxying, it will include the
"Proxy-QUIC-Forwarding" header in successful HTTP responses. The value
indicates whether or not the proxy supports forwarding. If the client does
not receive this header in responses, the client SHALL assume that the proxy
does not support this extension.

The client sends a REGISTER_CLIENT_CID capsule whenever it advertises a new
Client Connection ID to the target, and a REGISTER_TARGET_CID capsule when
it has received a new Target Connection ID for the target. In order to change
the connection ID bytes on the wire, a client can solicit new virtual connection
IDs by re-registering the same connection IDs. The client may solicit a new
Virtual Target Connection ID by sending a REGISTER_TARGET_CID capsule with a
previously registered Target Connection ID. Similarly, the client may solicit a
new Virtual Client Connection ID by sending a REGISTER_CLIENT_CID with a
previously registered Client Connection ID. The client MUST acknowledge the new
Virtual Client Connection ID with an ACK_CLIENT_VCID capsule or close the
registration. The proxy MUST NOT send in forwarded mode until ACK_CLIENT_VCID
has been received. Clients are responsible for changing Virtual Connection IDs
when the HTTP stream's network path changes to avoid linkability across network
paths. Note that initial REGISTER_CLIENT_CID capsules MAY be sent prior to
receiving an HTTP response from the proxy.

## New Proxied Connection Setup

To initiate QUIC-aware proxying, the client sends a REGISTER_CLIENT_CID
capsule containing the initial Client Connection ID that the client has
advertised to the target.

If the mapping is created successfully, the client will receive a
ACK_CLIENT_CID capsule that contains the same Client Connection ID that was
requested as well as a Virtual Client Connection ID that the client MUST use
when sending forwarding mode packets, assuming forwarding mode is supported.

If forwarding mode is supported, the client MUST respond with an
ACK_CLIENT_VCID to signal to the proxy that it may start sending forwarded mode
packets. If forwarding mode is not supported, an ACK_CLIENT_VCID capsule MUST
NOT be sent.

Since clients are always aware whether or not they are using a QUIC proxy,
clients are expected to cooperate with proxies in selecting Client Connection
IDs. A proxy detects a conflict when it is not able to create a unique mapping
using the Client Connection ID ({{conflicts}}). It can reject requests that
would cause a conflict and indicate this to the client by replying with a
CLOSE_CLIENT_CID capsule. In order to avoid conflicts, clients SHOULD select
Client Connection IDs of at least 8 bytes in length with unpredictable values.
A client also SHOULD NOT select a Client Connection ID that matches the ID used
for the QUIC connection to the proxy, as this inherently creates a conflict.

If the rejection indicated a conflict due to the Client Connection ID, the
client MUST select a new Connection ID before sending a new request, and
generate a new packet. For example, if a client is sending a QUIC Initial
packet and chooses a Connection ID that conflicts with an existing mapping
to the same target server, it will need to generate a new QUIC Initial.

## Adding New Client Connection IDs

Since QUIC connection IDs are chosen by the receiver, an endpoint needs to
communicate its chosen connection IDs to its peer before the peer can start
using them. In QUICv1, this is performed using the NEW_CONNECTION_ID frame.

Prior to informing the target of a new chosen client connection ID, the client
MUST send a REGISTER_CLIENT_CID capsule to the proxy containing the new Client
Connection ID.

The client should only inform the target of the new Client Connection ID once an
ACK_CLIENT_CID capsule is received that contains the echoed connection ID.

If forwarding mode is enabled, the client MUST reply to the ACK_CLIENT_CID with
an ACK_CLIENT_VCID capsule with the real and virtual connection IDs along with
an optional Stateless Reset Token.

## Sending With Forwarded Mode

Support for forwarded mode is determined by the "Proxy-QUIC-Forwarding" header,
see {{proxy-behavior}}.

Once the client has learned the target server's Connection ID, such as in the
response to a QUIC Initial packet, it can send a REGISTER_TARGET_CID capsule
containing the Target Connection ID to request the ability to forward packets.

The client MUST wait for an ACK_TARGET_CID capsule that contains the echoed
connection ID and Virtual Target Connection ID before using forwarded mode.

Prior to receiving the proxy server response, the client MUST send short header
packets tunnelled in HTTP Datagram frames. The client MAY also choose to tunnel
some short header packets even after receiving the successful response.

If the Target Connection ID registration is rejected, for example with a
CLOSE_TARGET_CID capsule, it MUST NOT forward packets to the requested Target
Connection ID, but only use tunnelled mode. The request might also be rejected
if the proxy does not support forwarded mode or has it disabled by policy.

QUIC long header packets MUST NOT be forwarded. These packets can only be
tunnelled within HTTP Datagram frames to avoid exposing unnecessary connection
metadata.

When forwarding, the client sends a QUIC packet with the Virtual Target
Connection ID in the QUIC short header, using the same socket between client and
proxy that was used for the main QUIC connection between client and proxy.

When forwarding, the proxy sends a QUIC packet with the Virtual Client Target
Connection ID in the QUIC short header, using the same socket between client
and proxy that was used for the main QUIC connection between client and proxy.

Prior to sending a forwarded mode packet, the sender MUST replace the Connection
ID with the Virtual Connection ID. If the Virtual Connection ID is larger than
the Connection ID, the sender MUST extend the length of the packet by the
difference between the two lengths, to include the entire Virtual Connection ID.
If the Virtual Connection ID is smaller than the Connection ID, the sender MUST
shrink the length of the packet by the difference between the two lengths.

Clients and proxies supporting forwarded mode MUST be able to handle Virtual
Connection IDs of different lengths than the corresponding Connection IDs.

## Receiving With Forwarded Mode

If the client has indicated support for forwarded mode with the "Proxy-QUIC-Forwarding"
header, the proxy MAY use forwarded mode for any Client Connection ID for which
it has a valid mapping.

Once a client has sent an ACK_CLIENT_VCID capsule to the proxy, it MUST be
prepared to receive forwarded short header packets on the socket between itself
and the proxy for the specified Virtual Client Connection ID.

The client uses the Destination Connection ID field of the received packet to
determine if the packet was originated by the proxy, or merely forwarded from
the target. The client replaces the Virtual Client Connection ID with the real
Client Connection ID before processing the packet further.

## Connection Maintenance in Forwarded Mode

When a client and proxy are using forwarded mode, it is possible that there can be
long periods of time in which no ack-eliciting packets (see {{Section 2 of !QUIC-RETRANSMISSION=RFC9002}}) are exchanged
between the client and proxy. If these periods extend beyond the effective idle
timeout for the client-to-proxy QUIC connection (see {{Section 10.1 of QUIC}}),
the QUIC connection might be closed by the proxy if the proxy does not use
forwarded packets as an explicit liveness signal. To avoid this, clients SHOULD
send keepalive packets to the proxy before the idle timeouts would be reached,
which can be done using a PING frame or another ack-eliciting frame as described
in {{Section 10.1.1 of QUIC}}.

# Proxy Behavior {#proxy-behavior}

Upon receipt of a CONNECT request that includes the "Proxy-QUIC-Forwarding"
header, the proxy indicates to the client that it supports QUIC-aware proxying
by including a "Proxy-QUIC-Forwarding" header in a successful response.
If it supports QUIC packet proxying in forwarded mode, it sets the value to "?1"; otherwise,
it sets it to "?0".

The proxy MUST include a "transform" parameter whose value is an `sf-string`
indicating the selected transform. If the proxy does not recognize or accept
any of the transforms offered by the client, it MUST omit this parameter and
set the header field value to "?0", or omit the header entirely.

Upon receipt of a REGISTER_CLIENT_CID or REGISTER_TARGET_CID capsule,
the proxy validates the registration and tries to establish the appropriate
mappings as described in {{mappings}}.

The proxy MUST reply to each REGISTER_CLIENT_CID capsule with either
an ACK_CLIENT_CID or CLOSE_CLIENT_CID capsule containing the
Connection ID that was in the registration capsule.

Similarly, the proxy MUST reply to each REGISTER_TARGET_CID capsule with
either an ACK_TARGET_CID or CLOSE_TARGET_CID capsule containing the
Connection ID that was in the registration capsule.

The proxy then determines the target-facing socket to associate with the
client's request. This will generally involve performing a DNS lookup for
the target hostname in the CONNECT request, or finding an existing target-facing
socket to the authority. The target-facing socket might already be open due to a
previous request from this client, or another. If the socket is not already
created, the proxy creates a new one. Proxies can choose to reuse target-facing
sockets across multiple UDP proxying requests, or have a unique target-facing socket
for every UDP proxying request.

If a proxy reuses target-facing sockets, it SHOULD store which authorities
(which could be a domain name or IP address literal) are being accessed over a
particular target-facing socket so it can avoid performing a new DNS query and
potentially choosing a different target server IP address which could map to a
different target server.

Target-facing sockets MUST NOT be reused across QUIC and non-QUIC UDP proxy
requests, since it might not be possible to correctly demultiplex or direct
the traffic. Any packets received on a target-facing socket used for proxying
QUIC that does not correspond to a known Connection ID MUST be dropped.

When the proxy recieves a REGISTER_CLIENT_CID capsule, it is receiving a
request to be able to route traffic matching the Client Connection ID back to
the client using. If the pair of this Client Connection ID and the selected
target-facing socket does not create a conflict, the proxy creates the mapping
and responds with an ACK_CLIENT_CID capsule. If forwarding mode is enabled, the
capsule contains a proxy-chosen Virtual Client Connection ID. If forwarding mode
is enabled, and after receiving an ACK_CLIENT_VCID capsule from the client, any
packets received by the proxy from the target-facing socket that match the
Client Connection ID can to be sent to the client after the proxy has replaced
the Connection ID with the Virtual Client Connection ID. If forwarding mode is
not supported, the proxy MUST NOT send a Virtual Client Connection ID by setting
the length to zero. The proxy MUST use tunnelled mode (HTTP Datagram frames) for
any long header packets. The proxy SHOULD forward directly to the client for any
matching short header packets if forwarding is supported by the client, but the
proxy MAY tunnel these packets in HTTP Datagram frames instead. If the mapping
would create a conflict, the proxy responds with a CLOSE_CLIENT_CID capsule.

When the proxy recieves a REGISTER_TARGET_CID capsule, it is receiving a
request to allow the client to forward packets to the target. The proxy
generates a Virtual Target Connection ID for the client to use when sending
packets in forwarded mode. If forwarded mode is not supported, the proxy MUST
NOT send a Virtual Target Connection ID by setting the length to zero. If
forwarded mode is supported, the proxy MUST use a Virtual Target Connection ID
that does not introduce a conflict with any other Connection ID on the
client-facing socket. The proxy creates the mapping and responds with an
ACK_TARGET_CID capsule. Once the successful response is sent, the proxy will
forward any short header packets received on the client-facing socket that use
the Virtual Target Connection ID using the correct target-facing socket after
first rewriting the Virtual Target Connection ID to be the correct Target
Connection ID.

Proxies MUST choose unpredictable Virtual Target and Client Connection IDs to
avoid forwarding loop attacks.

The proxy MUST only forward non-tunnelled packets from the client that are QUIC
short header packets (based on the Header Form bit) and have mapped Virtual Target
Connection IDs. Packets sent by the client that are forwarded SHOULD be
considered as activity for restarting QUIC's Idle Timeout {{QUIC}}.

## Removing Mapping State

For any registration capsule for which the proxy has sent an acknowledgement, any
mappings last until either endpoint sends a close capsule or the either side of the
HTTP stream closes.

A client that no longer wants a given Connection ID to be forwarded by the
proxy sends a CLOSE_CLIENT_CID or CLOSE_TARGET_CID capsule.

If a client's connection to the proxy is terminated for any reason, all
mappings associated with all requests are removed.

A proxy can close its target-facing socket once all UDP proxying requests mapped to
that socket have been removed.

## Handling Connection Migration

If a proxy supports QUIC connection migration, it needs to ensure that a migration
event does not end up sending too many tunnelled or proxied packets on a new
path prior to path validation.

Specifically, the proxy MUST limit the number of packets that it will proxy
to an unvalidated client address to the size of an initial congestion window.
Proxies additionally SHOULD pace the rate at which packets are sent over a new
path to avoid creating unintentional congestion on the new path.

When operating in forwarded mode, the proxy reconfigures or removes forwarding
rules as the network path between the client and proxy changes. In the event of
passive migration, the proxy automatically reconfigures forwarding rules to use
the latest active and validated network path for the HTTP stream. In the event of
active migration, the proxy removes forwarding rules in order to not send
packets with the same connection ID bytes over multiple network paths. After
initiating active migration, clients are no longer able to send forwarded mode
packets since the proxy will have removed forwarding rules. Clients can proceed with
tunnelled mode or can request new forwarding rules via REGISTER_CLIENT_CID and
REGISTER_TARGET_CID capsules. Each of the acknowledging capsules will contain new
virtual connection IDs to prevent packets with the same connection ID bytes being
used over multiple network paths. Note that the Client Connection ID and Target
Connection ID can stay the same while the Virtual Target Connection ID and
Virtual Client Connection ID change.

## Handling ECN Marking

Explicit Congestion Notification marking {{!ECN=RFC3168}} uses two bits in the IP
header to signal congestion from a network to endpoints. When using forwarded mode,
the proxy replaces IP headers for packets exchanged between the client and target;
these headers can include ECN markings. Proxies SHOULD preserve ECN markings on
forwarded packets in both directions, to allow ECN to function end-to-end. If the proxy does not
preserve ECN markings, it MUST set ECN marks to zero on the IP headers it generates.

Forwarded mode does not create an IP-in-IP tunnel, so the guidance in
{{?ECN-TUNNEL=RFC6040}} about transferring ECN markings between inner and outer IP
headers does not apply.

A proxy MAY additionally add ECN markings to signal congestion being experienced
on the proxy itself.

# Packet Transforms

A packet transform is the procedure applied to encode packets as they are sent
on the link between the client and proxy, along with the inverse decode step applied
on receipt. Simple transforms can be modeled as a function as follows:

Inputs:

1. A QUIC short header packet (after Connection ID remapping).
1. The mode (encode or decode).
1. The direction (client-to-proxy or proxy-to-client).
1. Any configuration information negotiated at startup.

Output:

* A UDP payload that conforms to the QUIC invariants {{?RFC8999}} and does not
  modify the Connection ID.

More complex transform behaviors could have internal state, but no such transforms
are presented here.

Packet transforms are identified by an IANA-registered name, and negotiated in
the HTTP headers (see {{client-behavior}}).  This document defines two initial
transforms: the `identity` transform and the `scramble` transform.

## The identify transform {#identity-transform}

The `identity` transform does not modify the packet in any way.  When this transform
is in use, a global passive adversary can trivially correlate pairs of packets
that crossed the forwarder, providing a compact proof that a specific client
was communicating to a specific target.

The `identity` transform is identified by the value "identity" {{iana-transforms}}.

Use of this transform is NOT RECOMMENDED if the `scramble` transform is supported
by both the client and the proxy. Implementations MAY choose to not implement or
support the `identity` transform, depending on the use cases and privacy requirements of
the deployment.

## The scramble transform {#scramble-transform}

The `scramble` transform implements length-preserving unauthenticated
re-encryption of QUIC packets while preserving the QUIC invariants.  When
the `scramble` transform is in use, a global passive adversary cannot simply compare the packet
contents on both sides of the proxy
to link the client and target.  However, the `scramble` transform does not defend against
analysis of packet sizes and timing, nor does it protect privacy against an
active attacker.

Deployments that implement the version of the `scramble` transform defined in this
document MUST use the value "scramble-dt". The finalized version is expected
to use the reserved value "scramble" {{iana-transforms}}.

The `scramble` transform is initialized using a 32-byte random symmetric key.
When offering or selecting this transform, the client and server each
generate the key that they will use to encrypt scrambled packets and MUST add it to the
Proxy-QUIC-Transform header in an `sf-binary` parameter named "scramble-key".
If either side receives a `scramble` transform without the "scramble-key" parameter,
forwarding mode MUST be disabled.

This transform relies on the AES-128 block cipher, which is represented by the
syntax `AES-ECB(key, plaintext_block)` as in {{?RFC9001}}.  The corresponding
decryption operation is written here as `AES-ECB-inv(key, ciphertext_block)`.
It also uses AES in Counter Mode ({{SP800-38A}}, Section 6.5), which is
represented by the syntax `AES-CTR(key, iv, input)` for encryption and
decryption (which are identical).  In this syntax, `iv` is an array of 16 bytes
containing the initial counter block.  The counter is incremented by the
standard incrementing function ({{SP800-38A}}, Appendix B.1) on the full block
width.

In brief, the transform applies AES in counter mode (AES-CTR) using an
initialization vector drawn from the packet, then encrypts the initialization
vector with AES-ECB. The detailed procedure is as follows:

1. Let `k1, k2 = scramble_key[:16], scramble_key[16:32]`.
1. Let `L` be the Connection ID length.
1. Let `cid = packet[1:L+1]`, i.e., the Connection ID.
1. Let `iv = packet[L+1:L+17]`, i.e., the 16 bytes following the Connection ID.
1. Let `ctr_input = packet[0] | packet[L+17:]`.
1. Let `ctr_output = AES-CTR(k1, iv, ctr_input)`.
1. Let `header = ctr_output[0] & 0x7F`.  This ensures that the Header Form bit
   is zero, as required by the QUIC invariants ({{?RFC8999}}, Section 5.2).
1. Encrypt `iv` with the block cipher: `encrypted_iv = AES-ECB(k2, iv)`.
1. Produce the output packet as:\\
   `header | cid | encrypted_iv | ctr_output[1:]`.

The inverse transform operates as follows:

1. Decrypt the AES-CTR initialization vector:\\
   `iv = AES-ECB-inv(k2, packet[L+1:L+17])`.
1. Compute the other variables exactly as in the forward transform.
   (AES-CTR encryption and decryption are identical.)
1. Produce the output: `header | cid | iv | ctr_output[1:]`.

The encryption keys used in this procedure do not depend on the packet contents,
so each party only needs to perform AES initialization once for each connection.

NOTE: The security of this arrangement relies on every short-header QUIC packet
containing a distinct 16 bytes following the Connection ID.  This is true
for the original ciphersuites of QUICv1, but it is not guaranteed by the QUIC
Invariants. Future ciphersuites and QUIC versions could in principle produce
packets that are too short or repeat the values at this location. When using the
`scramble` transform, clients MUST NOT offer any configuration that could
cause the client or target to violate this requirement.

# Example

Consider a client that is establishing a new QUIC connection through the proxy.
In this example, the client prefers the `scramble` transform, but also offers the `identity`
transform. It has selected a Client Connection ID of 0x31323334. In order to inform a proxy
of the new QUIC Client Connection ID, the client also sends a
REGISTER_CLIENT_CID capsule.

The client will also send the initial QUIC packet with the Long Header form in
an HTTP datagram.

~~~
Client                                             Server

STREAM(44): HEADERS             -------->
  :method = CONNECT
  :protocol = connect-udp
  :scheme = https
  :path = /target.example.com/443/
  :authority = proxy.example.org
  proxy-quic-forwarding = ?1; accept-transform=scramble,identity; \
      scramble-key=:abc...789=:
  capsule-protocol = ?1

STREAM(44): DATA                -------->
  Capsule Type = REGISTER_CLIENT_CID
  Connection ID = 0x31323334
  Stateless Reset Token = Token

DATAGRAM                        -------->
  Quarter Stream ID = 11
  Context ID = 0
  Payload = Encapsulated QUIC initial

           <--------  STREAM(44): HEADERS
                        :status = 200
                        proxy-quic-forwarding = ?1; \
                            transform=scramble; \
                            scramble-key=:ABC...321=:
                        capsule-protocol = ?1

           <--------  STREAM(44): DATA
                        Capsule Type = ACK_CLIENT_CID
                        Connection ID = 0x31323334
                        Virtual CID = 0x62646668
~~~

The proxy has acknowledged the Client Connection ID and provided a Virtual
Client Connection ID. Even if there were Short Header packets to send, the proxy
cannot send forwarded mode packets because the client hasn't acknowledged the
Virtual Client Connection ID.

~~~
STREAM(44): DATA                -------->
  Capsule Type = ACK_CLIENT_VCID
  Connection ID = 0x31323334
  Virtual CID = 0x62646668
  Stateless Reset Token = Token
~~~

The client acknowledges the Virtual Client Connection ID. The proxy still
doesn't have any Short Header Packets to send, but, if it did, it would be able
to send with forwarded mode.

~~~
/* Wait for target server to respond to UDP packet. */

           <--------  DATAGRAM
                        Quarter Stream ID = 11
                        Context ID = 0
                        Payload = Encapsulated QUIC initial

/* All Client -> Target QUIC packets must still be encapsulated  */

DATAGRAM                        -------->
  Quarter Stream ID = 11
  Context ID = 0
  Payload = Encapsulated QUIC packet

/* Forwarded mode packets possible in Target -> Client direction  */

           <--------  UDP Datagram
                        Payload = Forwarded QUIC SH packet

~~~

The client may receive forwarded mode packets from the proxy with a Virtual
Client Connection ID of 0x62646668 which it will replace with the real Client
Connection ID of 0x31323334. All forwarded mode packets sent by the proxy
will have been modified to contain the Virtual Client Connection ID instead
of the Client Connection ID, and processed by the negotiated "scramble"
packet transform. However, in the unlikely event that a forwarded packet
arrives before the proxy's HTTP response, the client will not know which
transform the proxy selected. In this case, the client will have to ignore
the packet or buffer it until the HTTP response is received.

Once the client learns which Connection ID has been selected by the target
server, it can send a new request to the proxy to establish a mapping for
forwarding. In this case, that ID is 0x61626364. The client sends the
following capsule:

~~~
STREAM(44): DATA                -------->
  Capsule Type = REGISTER_TARGET_CID
  Connection ID = 0x61626364

           <--------  STREAM(44): DATA
                        Capsule Type = ACK_TARGET_CID
                        Connection ID = 0x61626364
                        Virtual Target Connection ID = 0x123412341234
                        Stateless Reset Token = Token

/* Client -> Target QUIC short header packets may use forwarding mode */

UDP Datagram                     -------->
  Payload = Forwarded QUIC SH packet

~~~

Upon receiving an ACK_TARGET_CID capsule, the client starts sending Short Header
packets with a Destination Connection ID of 0x123412341234 directly to the proxy
(not tunnelled), and these are rewritten by the proxy to have the Destination
Connection ID 0x61626364 prior to being forwarded directly to the target. In the
reverse direction, Short Header packets from the target with a Destination
Connection ID of 0x31323334 are modified to replace the Destination Connection
ID with the Virtual Client Connection ID of 0x62646668 and forwarded directly to
the client.

# Packet Size Considerations

Since Initial QUIC packets must be at least 1200 bytes in length, the HTTP
Datagram frames that are used for a QUIC-aware proxy MUST be able to carry at least
1200 bytes.

Additionally, clients that connect to a proxy for purpose of proxying QUIC
SHOULD start their connection with a larger packet size than 1200 bytes, to
account for the overhead of tunnelling an Initial QUIC packet within an
HTTP Datagram frame. If the client does not begin with a larger packet size than
1200 bytes, it will need to perform Path MTU (Maximum Transmission Unit)
discovery to discover a larger path size prior to sending any tunnelled Initial
QUIC packets.

Once a proxied QUIC connections moves into forwarded mode, the client SHOULD
initiate Path MTU discovery to increase its end-to-end MTU.

# Security Considerations {#security}

Proxies that support this extension SHOULD provide protections to rate-limit
or restrict clients from opening an excessive number of proxied connections, so
as to limit abuse or use of proxies to launch Denial-of-Service attacks.

Sending QUIC packets by forwarding through a proxy without tunnelling exposes
clients to additional information exposure and deanonymization attacks which
need to be carefully considered. Analysis should consider both passive and
active attackers which may be global or localized to the network paths used
on one side of the proxy. The following sections highlight deanonymization risks with
using forwarded mode.

## Passive Attacks

A passive attacker aims to deanonymize a client by correlating traffic across
both sides of the proxy. When using forwarded mode with the `identity` packet
transform (see {{identity-transform}}), such correlation is trivial by matching
a subset of QUIC packet bytes as packets enter the proxy on one side and exit
on the other. Packet transforms such as `scramble` mitigate this by
cryptographically preventing such byte comparisons
(see {{!scramble-transform=scramble-transform}}).

Regardless of which packet transform is used, both tunnelled and forwarded mode
are still vulnerable to size and timing attacks, without the addition of techniques that go beyond the analysis
in this document, such as padding and adding chaff packets.  Such techniques could be supported
in future packet transforms, subject to additional security analysis.

Unlike tunnelled mode where packets are fully encapsulated in the client-to-proxy
connection, clients using forwarded mode to access multiple target servers
over the same client-to-proxy connection expose the number of target servers
they are communicating with on each connection to passive attackers that can
observe the client-to-proxy traffic. This additional metadata revealed on each
packet simplifies size and timing attacks.

## Active Attacks

An active attacker is an adversary that can inject, modify, drop, and view
packets in the network. Some active attacks have different effects between
forwarded mode and tunnelled mode, but active attacks can be used to correlate
flows in either mode.

Both tunnelled mode and forwarded mode (regardless of packet transform) are
vulnerable to packet injection in the target-to-client direction. An attacker
can inject a burst of packets with a known QUIC Connection ID and see which
Connection ID is used for the corresponding burst on the proxy-to-client network path.

Packet injection with a known QUIC Connection ID can also happen in the
client-to-proxy direction, which only affects forwarded mode since
tunnelled mode sends packets within an authenticated and integrity protected
QUIC connection to the proxy (see {{?RFC9001}}). None of the packet transforms
defined in this document provide integrity protection. Even if a packet
transform did provide integrity protection, attackers can inject replayed
packets. Protection against replayed packets is similarly provided by QUIC in
tunnelled mode, but not provided by any of the forwarded mode packet transforms
defined in this document.

An active attacker can modify packets in the client-to-proxy direction, which
would cause a tunnelling proxy to silently drop packets, while a forwarding proxy
would forward the packets. In this way, forwarded mode is less vulnerable to
flow recognition based on corrupting a portion of packets in a burst.

Chaining of proxies using forwarded mode introduces the risk of forwarding loop
attacks. Preventing Virtual Client Connection ID conflicts across proxies
sharing an IP address and port mitigates one such forwarding loop attack.
Conflicts can be avoided by partitioning the Virtual Client Connection ID space
across proxies, using sufficiently long and random values, or by other means.

[comment1]: # OPEN ISSUE: Figure out how clients and proxies could interact to
[comment2]: # learn whether an adversary is injecting malicious forwarded
[comment3]: # packets to induce rate limiting.

# IANA Considerations {#iana}

## HTTP Header {#iana-header}

This document registers the "Proxy-QUIC-Forwarding" header in the "Hypertext Transfer
Protocol (HTTP) Field Name Registry" <[](https://www.iana.org/assignments/http-fields)>.

~~~
    +-----------------------+----------+--------+---------------+
    | Header Field Name     | Protocol | Status |   Reference   |
    +-----------------------+----------+--------+---------------+
    | Proxy-QUIC-Forwarding |   http   |  exp   | This document |
    +-----------------------+----------+--------+---------------+
~~~
{: #iana-header-type-table title="Registered HTTP Header"}

## Proxy QUIC Forwarding Parameter Names

This document establishes a new registry, "Proxy QUIC Forwarding Parameter Names",
for parameter names to use with the `Proxy-QUIC-Forwarding` header field,
in <[](https://www.iana.org/assignments/masque/masque.xhtml)>.
Registrations in this registry are assigned using the
Specification Required policy (Section 4.6 of [IANA-POLICY]).

~~~
    +-----------------------+-------------------------------------+---------------+--------------------------------+
    | Parameter Name        | Description                         | Reference     | Notes                          |
    +-----------------------+-------------------------------------+---------------+--------------------------------+
    | accept-transform      | contains supported transforms       | This document | Section {{client-behavior}}    |
    +-----------------------+-------------------------------------+---------------+--------------------------------+
    | transform             | indicates selected transforms       | This document | Section {{proxy-behavior}}     |
    +-----------------------+-------------------------------------+---------------+--------------------------------+
    | scramble-key          | contains key for scramble transform | This document | Section {{scramble-transform}} |
    +-----------------------+-------------------------------------+---------------+--------------------------------+
~~~
{: #iana-parameter-names-table title="Initial Proxy QUIC Forwarding Parameter Names"}

## Packet Transform Names {#iana-transforms}

This document establishes a new registry for packet transform names
in <[](https://www.iana.org/assignments/masque/masque.xhtml)>
and defines two initial transforms: "identity" and "scramble".
Prior to finalization, deployments that implement the version of
the `scramble` transform defined in this document should use the value
"scramble-dt". Once the design team proposal is adopted and a new draft is submitted,
the wire identifier will become "scramble-XX" where XX is the draft number.
Registrations in this registry are assigned using the
Specification Required policy (Section 4.6 of [IANA-POLICY]).

| Transform Name | Description       | Specification | Notes                          |
|:---------------|:------------------|:--------------|--------------------------------|
| identity       | no transformation | This Document | Section {{identity-transform}}     |
| scramble       | Reserved (will be used for final version)  | This Document | Section {{scramble-transform}} |
{: #iana-packet-transforms-table title="Initial Packet Transform Names"}

## Capsule Types {#iana-capsule-types}

This document registers six new values in the "HTTP Capsule Types"
registry established by {{HTTP-DGRAM}}. Note that the codepoints below
will be replaced with lower values before publication.

|     Capule Type     |   Value   | Specification |
|:--------------------|:----------|:--------------|
| REGISTER_CLIENT_CID | 0xffe500  | This Document |
| REGISTER_TARGET_CID | 0xffe501  | This Document |
| ACK_CLIENT_CID      | 0xffe502  | This Document |
| ACK_CLIENT_VCID     | 0xffe503  | This Document |
| ACK_TARGET_CID      | 0xffe504  | This Document |
| CLOSE_CLIENT_CID    | 0xffe505  | This Document |
| CLOSE_TARGET_CID    | 0xffe506  | This Document |
{: #iana-capsule-type-table title="Registered Capsule Types"}

All of these new entries use the following values for these fields:

Status:

: provisional (permanent when this document is published)

Reference:

: This document

Change Controller:

: IETF

Contact:

: masque@ietf.org

Notes:

: None
{: spacing="compact" newline="false"}

--- back

# Acknowledgments {#acknowledgments}
{:numbered="false"}

Thanks to Lucas Pardue, Ryan Hamilton, and Mirja Kühlewind for their inputs
on this document.

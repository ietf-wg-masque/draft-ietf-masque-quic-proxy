---
title: QUIC-Aware Proxying Using HTTP
abbrev: QUIC Proxy
category: std
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

This document extends UDP Proxying over HTTP to add optimizations for proxied
QUIC connections. Specifically, it allows a proxy to reuse UDP 4-tuples for multiple
proxied connections, and adds a mode of proxying in which QUIC short header packets
can be forwarded and transformed through an HTTP/3 proxy rather than being fully
re-encapsulated and re-encrypted.

--- middle

# Introduction {#introduction}

UDP Proxying over HTTP {{!CONNECT-UDP=RFC9298}}
defines a way to send datagrams through an HTTP proxy, where UDP is used to communicate
between the proxy and a target server. This can be used to proxy QUIC
connections {{!QUIC=RFC9000}}, since QUIC runs over UDP datagrams.

This document uses the term "target" to refer to the server that a client is
accessing via a proxy. This target may be an origin server hosting content, or
another proxy for cases where proxies are chained together.

This document extends the UDP proxying protocol to add signalling about QUIC
Connection IDs. QUIC Connection IDs are used to identify QUIC connections in
scenarios where there is not a strict one-to-one mapping between QUIC
connections and UDP 4-tuples (pairs of IP addresses and ports).

If a client permits proxy port reuse, once a proxy is aware of QUIC Connection IDs,
it can reuse UDP 4-tuples between itself and a target for multiple proxied QUIC connections.

For proxies that are themselves running on HTTP/3 {{!HTTP3=RFC9114}}, and thus
are accessed by clients over QUIC, QUIC Connection IDs can be used to treat
packets differently on the link between clients and proxies. New QUIC Connection IDs
can be assigned to perform transformations to the packets that allow for efficient
forwarding of packets that don't require full re-encapsulation and re-encryption
of proxied QUIC packets within datagrams inside the QUIC connection between
clients and proxies.

This document defines two modes for proxying QUIC connections, "tunnelled" and
"forwarded":

1. Tunnelled is the default mode for UDP proxying, defined in {{CONNECT-UDP}}.
In this mode, packets in QUIC connection between the client and target are
encapsulated inside the QUIC connection between the client and proxy.
These packets use multiple layers of encryption and congestion control.

2. Forwarded is the mode of proxying added by this document. In this mode,
packets in the QUIC connection between the client and target are sent with dedicated
QUIC Connection IDs between the client and proxy, and use special-purpose
transforms instead of full re-encapsulation and re-encryption.

QUIC long header packets between clients and targets MUST be proxied in tunnelled
mode. QUIC short header packets between clients and targets MAY be proxied in
forwarded mode, subject to negotiation between a client and a proxy.

Forwarded mode is an optimization to reduce CPU and memory cost to clients and
proxies and avoid encapsulation overhead for packets on the wire that reduce
the effective MTU (Maximum Transmission Unit). This makes it suitable for
deployment situations that otherwise relied on cleartext TCP
proxies, which cannot support QUIC and have inferior security and privacy
properties.

The properties provided by the forwarded mode are as follows:

- All packets sent between the client and the target traverse through the proxy
device.
- The target server cannot know the IP address of the client solely based on the
proxied packets the target receives.
- Observers of either or both of the links between client and proxy and between
proxy and target are not able to learn more about the client-to-target
communication than if no proxy was used.

Forwarded mode does not prevent correlation of packets on the link between
client and proxy and the link between proxy and target by an entity that
can observe both links. The precise risks depend on the negotiated transform
({{transforms}}). See {{security}} for further discussion.

Both clients and proxies can unilaterally choose to disable forwarded mode for
any client-to-target connection.

The forwarded mode of proxying is only defined for HTTP/3 {{HTTP3}} and not
any earlier versions of HTTP.

QUIC proxies can proxy all versions of QUIC. See {{invariance}} for more information.

While Forwarded mode may improve overhead of per-packet processing, this
doesn't necessarily imply overall throughput is improved. Unlike tunnelled packets,
packets sent in Forwarded mode are not congestion controlled between client and
proxy. Deployments should consider whether or not the overhead advantages
outweigh potentially superior throughput afforded by client-to-proxy congestion
control.

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
- Client-to-proxy 4-tuple: the UDP 4-tuple (client IP address, client UDP port,
proxy IP address, proxy UDP port) used to communicate between the client and
the proxy.
- Proxy-to-target 4-tuple: the UDP 4-tuple (proxy IP address, proxy UDP port,
target IP address, target UDP port) used to communicate between the proxy and
the target.
- Client Connection ID (CID): a QUIC Connection ID that is chosen by the client, and
is used in the Destination Connection ID field of packets from the target to
the client.
- Target Connection ID (CID): a QUIC Connection ID that is chosen by the target, and
is used in the Destination Connection ID field of packets from the client to
the target.
- Virtual Connection ID (VCID): a fake QUIC Connection ID chosen by the proxy
that is used on the client-to-proxy 4-tuple in forwarded mode.
- Client VCID: a VCID used by the proxy to send forwarded packets from the target
to the client.
- Target VCID: a VCID used by the client to send forwarded packets to the target
via the proxy.
- Packet Transform: the procedure used to modify packets before they enter the
client-proxy link.

# Protocol Overview

QUIC-aware proxying involves a client, a proxy, and a target. Although
multiple proxies can be chained together in sequence (which is
a main motivation for enabling forwarded mode), each subsequent proxy
is just treated as a target by the preceding proxy.

~~~ aasvg
   +--------+              +-----------+              +--------+
   |        |              |           |              |        |
   | Client +--------------+   Proxy   +--------------+ Target |
   |        |              |           |              |        |
   +--------+              +-----------+              +--------+

       <----------- Client-to-target connection ----------->


       <-- Client-to-proxy -->       <-- Proxy-to-target -->
              4-tuple                        4-tuple
~~~
{: #overview-diagram title="Diagram of roles in QUIC-aware proxying"}

All QUIC-aware proxying relies on the proxy learning information about
QUIC connection IDs on the client-to-target QUIC connection ({{cid-awareness}}).

Forwarded mode adds the concept of Virtual Connection IDs that are assigned
by the proxy to use to identify packets on the client-to-proxy 4-tuple ({{vcids}}).

Negotiation of modes is described in {{negotiation}}, registration of connection
IDs in {{cid-registration}}, and forwarded mode in {{forwarded-mode}}.

## Connection ID Awareness {#cid-awareness}

For a proxy to be aware of proxied QUIC connection IDs, it needs to know and
correlate three values:

1. The HTTP stream used to proxy a client-to-target QUIC connection
1. The client-chosen connection ID on the client-to-target QUIC connection,
or the "client CID"
1. The target-chosen connection ID on the client-to-target QUIC connection,
or the "target CID"

For example, consider a proxy using HTTP/3 that has two clients (A and B) connected
simultaneously, each client coming from a different IP address and port.
Each client makes a request to proxy a UDP flow to "target.example.net" on
port 443. If the proxy knows that client A's connection to the target
has negotiated a client CID `AAAAAAAA` and a target CID `11111111`, and client B's
connection to the target has negotiated a client CID `BBBBBBBB` and a target CID
`22222222`, then the proxy would be able to use the same proxy-to-target 4-tuple
for both connections, because it can route packets from the target to the
correct client based on CID `AAAAAAAA` or `BBBBBBBB`.

~~~ aasvg
       <---------- Client A-to-target connection ---------->
       AAAAAAAA                                     11111111
   +--------+              +-----------+
   | Client +--------------+           +
   |   A    |              |           |
   +--------+              |           |              +--------+
                           |           |   Shared     |        |
                           |   Proxy   +--------------+ Target |
                           |           |   4-tuple    |        |
   +--------+              |           |              +--------+
   | Client |              |           |
   |   B    +--------------+           |
   +--------+              +-----------+
       BBBBBBBB                                     22222222
       <---------- Client B-to-target connection ---------->
~~~
{: #sharing-tuple-diagram title="Example of sharing a proxy-to-target 4-tuple"}

In order to share a proxy-to-target 4-tuple between multiple proxied connections,
the proxy MUST guarantee that the client CIDs do not conflict. See {{conflicts}}
for more discussion of handling CID conflicts.

## Virtual Connection IDs {#vcids}

Virtual Connection IDs (VCIDs) are QUIC Connection IDs used on the link between a
client and proxy that do not belong to the QUIC connection between the client
and proxy, but instead are aliases for particular client-to-target connections.
VCIDs are only used in forwarded mode. They are established using HTTP capsules
{{!HTTP-CAPSULES=RFC9297}} as described in {{vcid-issuance}}.

For example, consider a proxy using HTTP/3 that has a single client connected
to it. The client-to-proxy QUIC connection has `AAAAAAAA` as the client CID
and `BBBBBBBB` as the proxy CID. The client has connected to a single target
through the proxy, and the client-to-target QUIC connection has `CCCCCCCC`
as the client CID and `DDDDDDDD` as the target CID. In order to use
forwarded mode, the proxy assigns VCIDs to use on the client-to-proxy link
to represent the client-to-target connection. In this case, the VCIDs could
be `EEEEEEEE` for the client VCID and `FFFFFFFF` for the target VCID.

~~~ aasvg
   +--------+              +-----------+              +--------+
   |        |              |           |              |        |
   | Client +--------------+   Proxy   +--------------+ Target |
   |        |              |           |              |        |
   +--------+              +-----------+              +--------+

       AAAAAAAA       BBBBBBBB
       <-- Client-to-proxy -->
              connection

       CCCCCCCC                                     DDDDDDDD
       <----------- Client-to-target connection ----------->

  EEEEEEEE (CCCCCCCC)   FFFFFFFF (DDDDDDDD)
       <-- Client-to-proxy -->
                VCIDs
~~~
{: #vcid-diagram title="Diagram of VCIDs in forwarded mode"}

In order for a proxy to correctly route packets using VCIDs from
client-to-target and target-to-client, the proxy MUST guarantee that
the mappings between VCIDs, CIDs, and 4-tuples are unique. Specifically,
in order to route packets sent by the client, the proxy needs to be able
to observe the VCID and the client-to-proxy 4-tuple, and map them
to a specific target CID and proxy-to-target 4-tuple. In order to route
packets sent by a target, the proxy needs to be able to observe the client
CID and the proxy-to-target 4-tuple, and map them to a specific VCID
and client-to-proxy 4-tuple. Since proxies choose the VCID values, they
can ensure that the VCIDs are distinguishable.

Servers receiving QUIC packets can employ load balancing
strategies such as those described in {{?QUIC-LB=I-D.ietf-quic-load-balancers}}
that encode routing information in the connection ID. When operating in
forwarded mode, clients send QUIC packets destined for the target directly
to the proxy. Since these packets are generated using the target CID,
load balancers may not have the necessary information to route packets to the correct proxy. The target VCID
is a VCID chosen by the proxy that the client uses when sending
forwarded mode packets. The proxy replaces the target VCID
with the target CID prior to forwarding the packet to the target.

Similarly, QUIC requires that connection IDs aren't reused over multiple network
paths to avoid linkability. The client VCID is a connection ID
chosen by the proxy that the proxy uses when sending forwarded mode packets.
The proxy replaces the client CID with the client VCID prior to
forwarding the packet to the client. Clients take advantage of this
to avoid linkability when migrating a client to proxy network path. The client
VCID allows the connection ID bytes to change on the wire without requiring the
connection IDs on the client-to-target connection to change.
To reduce the likelihood of connection ID conflicts, the proxy MUST choose a
client VCID that is at least as long as the original client CID. Similarly,
clients multiplexing connections on the same UDP 4-tuple SHOULD
choose a client CID that's sufficiently long to reduce the likelihood
of a conflict with the proxy-chosen client VCID. For proxies that share a
client-facing IP and port with other proxies, support target-facing port sharing,
and cannot guarantee there are no proxies being proxied to, the client VCID MUST be
constructed such that it is unpredictable to the client or to guarantee no
conflicts among all proxies sharing an IP address and port. For such proxies, a
client VCID MUST NOT be equal to the original client CID. See
{{security}} for more discussion on client VCID construction.

Clients and Proxies not implementing forwarded mode do not need to consider
VCIDs since all client-to-target datagrams will be encapsulated
within the client-to-proxy connection.

# Negotiating Modes {#negotiation}

In order to support QUIC-aware proxying, both clients and proxies need
to support capsules {{HTTP-CAPSULES}}, which is indicated by including
the "Capsule-Protocol" header field in requests and responses. If this header
field is not included, none of the functionality in this document can be used.

~~~
  capsule-protocol = ?1
~~~

To permit the proxy to share target-facing ports, the client needs to include the
"Proxy-QUIC-Port-Sharing" header field, as defined in {{port-sharing-header}}.
This indicates that the proxy may share target-facing 4-tuples concurrently with
other QUIC connections. Clients that do not want the target-facing 4-tuple shared
will not include this header or will provide it with a value of "?0".

~~~
  proxy-quic-port-sharing = ?1
~~~

To support forwarded mode, both clients and proxies need to include
the "Proxy-QUIC-Forwarding" header field, as defined in {{forwarding-header}}.
This indicates support for forwarded mode, and allows negotiation of
packet transforms to apply when forwarding ({{transforms}}), along
with any parameters for specific transforms. Clients or proxies that
don't support forwarded mode omit this header field or set it to "?0".

~~~
  proxy-quic-forwarding = ?1; \
      accept-transform="scramble-dt,identity"; \
      scramble-key=:abc...789=:
~~~

If neither header is supplied with a value of "?1", none of the functionality
in this document can be used and handling reduces to normal connect-udp.

After negotiating support with header fields, clients and proxies use
the capsules defined in {{cid-registration}} and {{forwarded-mode}} to
communicate information about CIDs and VCIDs.

## Proxy-QUIC-Forwarding Header {#forwarding-header}

A client initiates UDP proxying via a CONNECT request as defined
in {{CONNECT-UDP}}. Within its request, it includes the "Proxy-QUIC-Forwarding"
header to indicate whether or not the request should support forwarding.

"Proxy-QUIC-Forwarding" is an Item Structured Header {{!RFC8941}}. Its
value MUST be a Boolean.

If the client wants to enable QUIC packet forwarding for this request, it sets
the value to "?1". Otherwise, it sets the value to "?0" or omits the header.

If advertising support for forwarding, the client MUST add an "accept-transform" parameter whose value is a
String containing the supported packet transforms ({{transforms}})
in order of descending preference, separated by commas. If the proxy receives a
"Proxy-QUIC-Forwarding" header with a value of "?1" and without the "accept-transform" parameter, it
MUST ignore the header and respond as if the client had not sent the
"Proxy-QUIC-Forwarding" header.

If advertising support for forwarding, the client MAY add an "active-vcid-limit"
parameter whose value is an Integer indicating the maximum number of active
Virtual Connection IDs that the proxy can issue for each registered connection
ID ({{vcid-limit}}). The value MUST be at least 2. If the parameter is absent, a
limit of 2 is assumed. If the proxy receives an "active-vcid-limit" parameter
whose value is not an Integer or is less than 2, it MUST ignore the header and
respond as if the client had not sent the "Proxy-QUIC-Forwarding" header.

If the proxy supports forwarded mode for the request, it will include the
"Proxy-QUIC-Forwarding" header with a value of "?1" in successful HTTP
responses. If the client does not receive this header with a value of "?1", the
client SHALL assume that the proxy does not support forwarded mode. If the
client receives a transform that it did not advertise support for, it MUST
abort the request.

The proxy MUST include a "transform" parameter whose value is a String
indicating the selected transform. If the proxy does not recognize or accept
any of the transforms offered by the client, it MUST omit this parameter and
set the header field value to "?0", or omit the header entirely.

Clients MUST NOT send the "transform" parameter and proxies MUST NOT send the
"accept-transform" or "active-vcid-limit" parameters. Clients MUST ignore
receipt of an "accept-transform" or "active-vcid-limit" parameter and proxies
MUST ignore receipt of a "transform" parameter.

## Proxy-QUIC-Port-Sharing Header {#port-sharing-header}

A client may include the "Proxy-QUIC-Port-Sharing" header to indicate whether
or not the proxy is permitted to share ports between this QUIC connection and other
proxied QUIC connections.

"Proxy-QUIC-Port-Sharing" is an Item Structured Header {{!RFC8941}}. Its value
MUST be a Boolean.

Clients SHOULD send this with a value of "?1" unless the client wishes to prohibit
this behavior. Permitting the proxy to share ports may allow the proxy to conserve
resources and support more clients. Clients should not advertise support for port
sharing unless they are willing to share the same 4-tuple when communicating with
the target. Sharing ports with other QUIC connections may result in fate-sharing
with clients that might be considered to be untrusted or malicious by the target. Such
fate-sharing may impact performance or may lead to being misclassified as
malicious.

A proxy that supports port sharing for the request includes
"Proxy-QUIC-Port-Sharing" with a value of "?1" in its response.
A proxy that does not support port sharing, SHOULD send "Proxy-QUIC-Port-Sharing"
with a value of "?0". Doing so allows clients to stop sending capsules for this
extension if forwarding mode is also not supported.

When port sharing is supported and forwarded mode is not, registration of target
Connection IDs is permitted, but is not required since port sharing only requires
demultiplexing QUIC packets in the target-to-client direction.

# Connection ID Registration {#cid-registration}

Connection ID awareness relies on using capsules {{HTTP-CAPSULES}} to
signal addition and removal of Connection IDs. Clients send capsules
to let proxies know when Connection IDs on the client-to-target
QUIC connection are changing. Proxies send capsules to acknowledge or
reject these Connection IDs.

Note that these capsules do not register contexts. QUIC packets are encoded
using HTTP Datagrams with the context ID set to zero as defined in
{{CONNECT-UDP}}.

The REGISTER_CLIENT_CID ({{capsule-reg-client}}) and REGISTER_TARGET_CID
({{capsule-reg-target}}) capsule types allow a client to inform
the proxy about a new client CID or a new target CID,
respectively. These capsule types MUST only be sent by a client. Each
registration capsule carries the sequence number of the registration, which
other capsules use to refer to it. Client CID registrations and target CID
registrations have separate sequence number spaces, which allows the proxy to
limit the number of registrations of each type independently. The first
registration of each type has sequence number 0, and each subsequent
registration of the same type has a sequence number one greater than the
previous one. Every registration capsule consumes a sequence number, including
registrations that are rejected. A proxy that receives a registration capsule
whose sequence number is not the next one for that type of registration, or is
not less than the limit that it has advertised for that type, MUST reset the
stream with H3_DATAGRAM_ERROR error code.

The ACK_CLIENT_CID and ACK_TARGET_CID capsule types ({{capsule-ack-cid}}) are
sent by the proxy to the client to indicate that a mapping was successfully
created for a registered connection ID. These capsule types MUST only be sent by
a proxy.

The REJECT_CLIENT_CID and REJECT_TARGET_CID capsule types ({{capsule-reject}})
are used to reject connection ID registrations. Each capsule includes
a reason code indicating the reason for the rejection. These capsules MUST only be sent
by the proxy.

A proxy MUST NOT send an acknowledgement or rejection capsule for a registration
that the client has not sent, or that the proxy has already acknowledged or
rejected. If a client receives such a capsule, it MUST reset the stream with
H3_DATAGRAM_ERROR error code.

The RETIRE_CLIENT_CID and RETIRE_TARGET_CID capsule types ({{capsule-retire-cid}})
are used by the client to remove connection ID registrations, typically because
the connection ID was retired on the client-to-target connection. These capsule
types MUST only be sent by a client.

The MAX_CLIENT_CIDS and MAX_TARGET_CIDS capsule types ({{capsule-max-cids}})
MUST only be sent by the proxy. They indicate to the client the cumulative
number of client CID and target CID registrations, respectively, that the client
is allowed to request. The initial maximum for each type is 2, allowing the
client to send 2 registrations of each type, one with sequence number 0 and
another with sequence number 1. These capsules are only sent to increase the
limit.

When port sharing {{port-sharing-header}} is supported, the client MUST register
and receive acknowledgements for client CIDs before using them. Packets with
unknown connection IDs received by the proxy on a target-facing sockets that support
port sharing MUST be dropped. In order to avoid introducing an additional round trip
on setup, a REGISTER_CLIENT_CID capsule SHOULD be sent at the same time as the client's
first flight. If the proxy rejects the client CID, the proxy MUST drop all packets until
it has sent an ACK_CLIENT_CID capsule and the client MUST NOT send any packets until
receiving an ACK_CLIENT_CID. When port sharing is supported, a proxy SHOULD buffer a
reasonable number of incoming packets while waiting for the first REGISTER_CLIENT_CID
capsule.

Importantly, registering connection IDs does not introduce any delay in
communication between client and target unless port sharing is supported and
there is an unlikely client CID collision. The client and target can always
communicate over the tunnel without having to wait for registrations to be
acknowledged.

For QUIC-aware proxying without forwarded mode, the steps are as follows:

1. The client sends the `REGISTER_CLIENT_CID` capsule once it selects a
CID that it will use for receiving packets from a target.

1. The proxy sends the `ACK_CLIENT_CID` capsule to acknowledge that CID;
alternatively, the proxy can send the
`REJECT_CLIENT_CID` if it detects a conflict with another CID.

1. The proxy sends `MAX_CLIENT_CIDS` and `MAX_TARGET_CIDS` capsules to allow
additional registrations via future `REGISTER_CLIENT_CID` and
`REGISTER_TARGET_CID` capsules.

1. Whenever a client stops using a particular CID, the client
sends a `RETIRE_CLIENT_CID`. The client can also initiate new
`REGISTER_CLIENT_CID` exchanges at any time.

## Capsule Types and Formats {#capsule-types-formats}

### REGISTER_CLIENT_CID {#capsule-reg-client}

The REGISTER_CLIENT_CID capsule is sent by the client and contains a sequence
number and a single connection ID that is the client-provided connection ID on
the client-to-target QUIC connection.

~~~
Register Client CID Capsule {
  Type (i) = see {{iana}} for the value of the capsule type
  Length (i),
  Connection ID Sequence Number (i),
  Connection ID (0..2040),
}
~~~
{: #fig-capsule-register-client-cid title="Register Client CID Capsule Format"}

Connection ID Sequence Number:
: The sequence number of this registration in the sequence number space of
client CID registrations ({{cid-registration}}).

Connection ID:
: A connection ID being registered, which is between 0 and 255 bytes in
length. The length of the connection ID is implied by the length of the
capsule. Note that in QUICv1, the length of the Connection ID is limited
to 20 bytes, but QUIC invariants allow up to 255 bytes.

### REGISTER_TARGET_CID {#capsule-reg-target}

The REGISTER_TARGET_CID capsule is sent by the client and includes a sequence
number, the target-provided connection ID on the client-to-target QUIC
connection, and the corresponding Stateless Reset Token.

~~~
Register Target CID Capsule {
  Type (i) = see {{iana}} for the value of the capsule type
  Length (i),
  Connection ID Sequence Number (i),
  Connection ID Length (i),
  Connection ID (0..2040),
  Stateless Reset Token (..),
}
~~~
{: #fig-capsule-register-target-cid title="Register Target CID Capsule Format"}

Connection ID Sequence Number:
: The sequence number of this registration in the sequence number space of
target CID registrations ({{cid-registration}}).

Connection ID Length:
: The length of the connection ID being registered, which is between 0 and
255. Note that in QUICv1, the length of the Connection ID is limited to 20
bytes, but QUIC invariants allow up to 255 bytes.

Connection ID:
: A connection ID being registered whose length is equal to Connection ID
Length. This is the real target CID.

Stateless Reset Token:
: The target-provided Stateless Reset token allowing the proxy to correctly
recognize Stateless Reset packets to be tunnelled to the client. The length of
the Stateless Reset Token is implied by the length of the capsule.

### ACK_CLIENT_CID and ACK_TARGET_CID {#capsule-ack-cid}

The ACK_CLIENT_CID and ACK_TARGET_CID capsules are sent by the proxy in
response to REGISTER_CLIENT_CID and REGISTER_TARGET_CID capsules, respectively,
to acknowledge the registration of a connection ID.

~~~
Acknowledge CID Capsule {
  Type (i) = see {{iana}} for the values of the capsule types
  Length (i),
  Connection ID Sequence Number (i),
}
~~~
{: #fig-capsule-ack-cid title="Acknowledge CID Capsule Format"}

Connection ID Sequence Number:
: The sequence number of the registration being acknowledged, in the sequence
number space of client CID registrations for ACK_CLIENT_CID and of target CID
registrations for ACK_TARGET_CID ({{cid-registration}}).

### REJECT_CLIENT_CID and REJECT_TARGET_CID {#capsule-reject}

REJECT_CLIENT_CID and REJECT_TARGET_CID capsule types include a reason code
and the sequence number of a registration. Proxies send these capsules to reject
connection ID registrations.

~~~
Reject CID Capsule {
  Type (i) = see {{iana}} for the values of the capsule types
  Length (i),
  Reason (i),
  Connection ID Sequence Number (i),
}
~~~
{: #fig-capsule-reject-cid title="Reject CID Capsule Format"}

Reason:
: The reason for rejecting the connection ID registration.
See {{iana-cid-reasons}} for the list of reason codes.

Connection ID Sequence Number:
: The sequence number of the registration being rejected, in the sequence
number space of client CID registrations for REJECT_CLIENT_CID and of target
CID registrations for REJECT_TARGET_CID ({{cid-registration}}).

### RETIRE_CLIENT_CID and RETIRE_TARGET_CID {#capsule-retire-cid}

RETIRE_CLIENT_CID and RETIRE_TARGET_CID capsule types include the sequence
number of a registration. Clients send these capsules to remove the registration
of a connection ID that they no longer need.

~~~
Retire CID Capsule {
  Type (i) = see {{iana}} for the values of the capsule types
  Length (i),
  Connection ID Sequence Number (i),
}
~~~
{: #fig-capsule-retire-cid title="Retire CID Capsule Format"}

Connection ID Sequence Number:
: The sequence number of the registration being retired, in the sequence number
space of client CID registrations for RETIRE_CLIENT_CID and of target CID
registrations for RETIRE_TARGET_CID ({{cid-registration}}).

### MAX_CLIENT_CIDS and MAX_TARGET_CIDS {#capsule-max-cids}

The MAX_CLIENT_CIDS and MAX_TARGET_CIDS capsules are sent by the proxy to the
client to define the cumulative number of client CID and target CID
registrations, respectively, that the client is allowed to request.

~~~
Maximum Connection IDs Capsule {
  Type (i) = see {{iana}} for the values of the capsule types
  Length (i),
  Maximum Connection IDs (i),
}
~~~
{: #fig-capsule-max-connection-ids title="Maximum Connection IDs Capsule Format"}

Maximum Connection IDs:
: A count of the cumulative number of registrations of the corresponding type
that the client is allowed to request. For example, if the value of a
MAX_CLIENT_CIDS capsule is 4, the maximum allowed sequence number for a client
CID registration would be 3.

The value advertised in the capsule MUST be greater than any value previously
sent in a capsule of the same type, and MUST be greater than the initial
allowed limit of 2. Thus, any value sent in the capsule MUST be at least 3.

Clients receiving a MAX_CLIENT_CIDS or MAX_TARGET_CIDS capsule with an invalid
value MUST reset the stream with H3_DATAGRAM_ERROR error code.

## Client Considerations

The client sends a REGISTER_CLIENT_CID capsule before it advertises a new
client CID to the target, and a REGISTER_TARGET_CID capsule when
it has received a new target CID for the target. When a connection ID is
retired on the client-to-target connection, the client sends the corresponding
RETIRE_CLIENT_CID or RETIRE_TARGET_CID capsule. Note that initial
REGISTER_CLIENT_CID capsules MAY be sent prior to receiving an HTTP response
from the proxy.

A client MUST NOT register a connection ID that is already registered on the
same request.

Connection ID registrations are subject to proxy-advertised limits. Each
registration has a corresponding sequence number ({{cid-registration}}). The
client MUST NOT send a registration capsule with a sequence number greater than
or equal to the value the proxy advertises for that type of registration via the
MAX_CLIENT_CIDS or MAX_TARGET_CIDS capsule. The initial limit for each type is
2, allowing sequence numbers 0 and 1 for a total of two registrations of each
type without receiving a MAX_CLIENT_CIDS or MAX_TARGET_CIDS capsule from the
proxy.

A client that cannot register a new target CID due to the MAX_TARGET_CIDS limit
uses tunnelled mode for packets that use that target CID. A client that cannot
register a new client CID within a reasonable time due to the MAX_CLIENT_CIDS
limit, and cannot continue without it, SHOULD abort the proxied connection by
resetting the HTTP stream with the H3_NO_ERROR error code.

### New Proxied Connection Setup {#connection-setup}

To initiate QUIC-aware proxying, the client sends a REGISTER_CLIENT_CID
capsule containing the initial client CID that the client has
advertised to the target.

If the mapping is created successfully, the client will receive an
ACK_CLIENT_CID capsule that contains the sequence number of that
registration.

Since clients are always aware whether or not they are using a QUIC proxy,
clients are expected to cooperate with proxies in selecting client CIDs.
A proxy detects a conflict when it is not able to create a unique mapping
using the client CID ({{conflicts}}). It can reject registrations that
would cause a conflict by replying with a REJECT_CLIENT_CID capsule with the
CONFLICT reason code. Proxies may also reject registrations for short CIDs
using the TOO_SHORT reason code. In order to avoid rejections, clients SHOULD
select client CIDs of at least 8 bytes in length with unpredictable values.
A client also SHOULD NOT select a client CID that matches the ID used
for the QUIC connection to the proxy, as this inherently creates a conflict.

If the rejection reason was CONFLICT, the client MUST select a new Connection ID
before sending a new registration request, and generate a new packet. For example,
if a client is sending a QUIC Initial packet and chooses a Connection ID that
conflicts with an existing mapping to the same target server, it will need to
generate a new QUIC Initial. If the rejection reason was TOO_SHORT, the client
MUST select a longer Connection ID before retrying.

### Adding New Client Connection IDs

Since QUIC connection IDs are chosen by the receiver, an endpoint needs to
communicate its chosen connection IDs to its peer before the peer can start
using them. In QUICv1, this is performed using the NEW_CONNECTION_ID frame.

Prior to informing the target of a new chosen client CID, the client
MUST send a REGISTER_CLIENT_CID capsule to the proxy containing the new client
CID.

The client should only inform the target of the new client CID once it has
received an ACK_CLIENT_CID capsule for the registration.

## Proxy Considerations

The proxy MUST reply to each REGISTER_CLIENT_CID capsule with either
an ACK_CLIENT_CID or REJECT_CLIENT_CID capsule containing the
sequence number of the registration.

Similarly, the proxy MUST reply to each REGISTER_TARGET_CID capsule with
either an ACK_TARGET_CID or REJECT_TARGET_CID capsule containing the
sequence number of the registration.

A proxy that receives a REGISTER_CLIENT_CID or REGISTER_TARGET_CID capsule for a
connection ID that is already registered on the same request MUST reset the
stream with H3_DATAGRAM_ERROR error code.

A proxy that receives a RETIRE_CLIENT_CID or RETIRE_TARGET_CID capsule with a
sequence number that the client has not yet used for that type of registration
MUST reset the stream with H3_DATAGRAM_ERROR error code. A proxy ignores these
capsules for registrations that the client has already retired, or that the
proxy has rejected, which can happen when the rejection and retirement capsules
are sent simultaneously.

The proxy then determines the proxy-to-target 4-tuple to associate with the
client's request. This will generally involve performing a DNS lookup for
the target hostname in the CONNECT request, or finding an existing proxy-to-target
4-tuple to the authority. The proxy-to-target 4-tuple might already be open due to a
previous request from this client, or another. If the 4-tuple is not already
created, the proxy creates a new one. Proxies can choose to reuse proxy-to-target
4-tuples across multiple UDP proxying requests, or have a unique proxy-to-target 4-tuple
for every UDP proxying request. If the client did not send a value of "?1" for the
"Proxy-QUIC-Port-Sharing" header, port reuse is not permitted and the proxy MUST allocate
a new UDP 4-tuple.

If a proxy reuses proxy-to-target 4-tuples, it SHOULD store which authorities
(which could be a domain name or IP address literal) are being accessed over a
particular proxy-to-target 4-tuple so it can avoid performing a new DNS query and
potentially choosing a different target server IP address which could map to a
different target server.

Proxy-to-target 4-tuples MUST NOT be reused across QUIC and non-QUIC UDP proxy
requests, since it might not be possible to correctly demultiplex or direct
the traffic. Any packets received on a proxy-to-target 4-tuple used for proxying
QUIC that does not correspond to a known CID MUST be dropped.

When the proxy receives a REGISTER_CLIENT_CID capsule, it is receiving a
request to be able to route traffic matching the client CID back to
the client. If the pair of this client CID and the selected
proxy-to-target 4-tuple does not create a conflict, the proxy creates the mapping
and responds with an ACK_CLIENT_CID capsule. If the mapping
would create a conflict, the proxy responds with a REJECT_CLIENT_CID capsule
with the CONFLICT reason code.

When the proxy receives a REGISTER_TARGET_CID capsule, it creates the mapping
and responds with an ACK_TARGET_CID capsule, or responds with a
REJECT_TARGET_CID capsule if it cannot create the mapping, such as due to a
conflict ({{conflicts}}).

In order to permit the client to change client-to-target connection IDs, the proxy
SHOULD send MAX_CLIENT_CIDS and MAX_TARGET_CIDS capsules allowing the client
additional connection ID registrations.

### Detecting Conflicts {#conflicts}

In order to be able to route packets correctly in both tunnelled and forwarded
mode, proxies check for conflicts before creating a new CID mapping. If a conflict
is detected, the proxy will reject the client's registration using a REJECT_CLIENT_CID
or REJECT_TARGET_CID capsule with the CONFLICT reason code.

Two 4-tuples conflict if and only if all members of the 4-tuple (local IP
address, local UDP port, remote IP address, and remote UDP port) are identical.

Two Connection IDs conflict if and only if one Connection ID is equal to or a
prefix of another. For example, a zero-length Connection ID conflicts with all
connection IDs. This definition of a conflict originates from the fact that
QUIC short headers do not carry the length of the Destination Connection ID
field, and therefore if two short headers with different Destination Connection
IDs are received on a shared 4-tuple, one being a prefix of the other prevents
the receiver from identifying which mapping this corresponds to.

The proxy treats two mappings as being in conflict when a conflict is detected
for all elements on the left side of the mapping diagrams above.

Since very short Connection IDs are more likely to lead to conflicts,
particularly zero-length Connection IDs, a proxy MAY choose to reject
registrations for very short Connection IDs using the TOO_SHORT reason code.


### Stateless Resets from the Target {#target-resets}

Reuse of proxy-to-target 4-tuples is only possible because QUIC connection IDs
allow distinguishing packets for multiple QUIC connections received with the
same 5-tuple. One exception to this is Stateless Reset packets, in which the
connection ID is not used, but rather populated with unpredictable bits followed
by a Stateless Reset token, to make it indistinguishable from a regular packet
with a short header. In order for the proxy to correctly recognize Stateless
Reset packets, the client SHOULD share the Stateless Reset token for each
registered target CID. When the proxy receives a Stateless Reset packet, it
sends the packet to the client as a tunnelled datagram.

### Closing Proxy State

For any registration capsule for which the proxy has sent an acknowledgement, the
mapping lasts until the client retires it or either side of the
HTTP stream closes.

If a client's connection to the proxy is terminated for any reason, all
mappings associated with all requests are removed.

A proxy can close its proxy-to-target 4-tuple once all UDP proxying requests mapped to
that 4-tuple have been removed.

# Using Forwarded Mode {#forwarded-mode}

Forwarded mode builds on Connection ID registration ({{cid-registration}}): for
each registered connection ID, the proxy issues Virtual Connection IDs that are
used on the client-to-proxy 4-tuple in its place.

When forwarded mode is enabled, the proxy issues Virtual Connection IDs using
the NEW_TARGET_VCID ({{capsule-new-target-vcid}}) and NEW_CLIENT_VCID
({{capsule-new-client-vcid}}) capsule types, and the client accepts or refuses
each client VCID using the ACK_CLIENT_VCID ({{capsule-ack-client-vcid}}) and
REJECT_CLIENT_VCID ({{capsule-reject-client-vcid}}) capsule types. The client
retires target VCIDs using the RETIRE_TARGET_VCID capsule type
({{capsule-retire-target-vcid}}), and the proxy retires client VCIDs using the
RETIRE_CLIENT_VCID capsule type ({{capsule-retire-client-vcid}}). These
capsule types MUST only be sent when forwarded mode is enabled.
{{vcid-issuance}} and {{vcid-retirement}} describe how they are used.

All packets sent in forwarded mode use a transform in which CIDs are switched
into VCIDs, and the contents of packets are either left the same, or modified
({{transforms}}).

Forwarded mode also raises special considerations for handling connection
maintenance ({{maintenance}}), connection migration ({{migration}}),
server preferred addresses ({{preferred-address}}), ECN markings ({{ecn}}),
and stateless resets ({{resets}}).

Forwarded mode packets are not part of the QUIC connection the tunnel is
managed by, but instead an independent flow of QUIC packets.

For QUIC-aware proxying with forwarded mode, the steps are as follows:

1. The client sends the `REGISTER_CLIENT_CID` capsule once it selects a
CID that it will use for receiving packets from a target.

1. The proxy sends the `ACK_CLIENT_CID` capsule to acknowledge that CID;
alternatively, the proxy can send the
`REJECT_CLIENT_CID` if it detects a conflict with another CID.

1. The proxy sends one or more `NEW_CLIENT_VCID` capsules, each proposing a
client VCID for that client CID.

1. The client sends an `ACK_CLIENT_VCID` capsule for each client VCID that it
can use, which allows the proxy to send forwarded packets using that client
VCID, or a `REJECT_CLIENT_VCID` capsule otherwise.

1. The client sends the `REGISTER_TARGET_CID` capsule as soon as it learns
the target CID on the client-to-target connection.

1. The proxy sends the `ACK_TARGET_CID` capsule to acknowledge that CID;
alternatively, the proxy can send the
`REJECT_TARGET_CID` if it detects a conflict with another CID.

1. The proxy sends one or more `NEW_TARGET_VCID` capsules for that target CID. Once
the client receives a target VCID, it can start sending forwarded
packets using the target VCID.

1. The proxy sends `MAX_CLIENT_CIDS` and `MAX_TARGET_CIDS` capsules to allow
additional registrations via future `REGISTER_CLIENT_CID` and
`REGISTER_TARGET_CID` capsules.

1. When the client migrates to a new network path, the client and proxy switch
to Virtual Connection IDs they have not used before, and retire the ones they no
longer use ({{migration}}). When the proxy needs to stop accepting
particular target VCIDs, such as when rotating the keys it uses to generate
VCIDs, it sends a `NEW_TARGET_VCID` capsule that asks the client to retire them.

1. Whenever a client or target stops using a particular CID, the client
sends a `RETIRE_CLIENT_CID` or `RETIRE_TARGET_CID` capsule. The client
can also initiate new `REGISTER_CLIENT_CID` or `REGISTER_TARGET_CID`
exchanges at any time.

## Virtual Connection ID Capsule Types and Formats {#vcid-capsule-types-formats}

### NEW_TARGET_VCID {#capsule-new-target-vcid}

The NEW_TARGET_VCID capsule is sent by the proxy to issue a target VCID for a
registered target CID, along with a Stateless Reset Token for it. It can also
ask the client to retire target VCIDs that the proxy issued earlier for the same
target CID ({{vcid-request-retirement}}). This capsule MUST only be sent by the
proxy.

~~~
New Target VCID Capsule {
  Type (i) = see {{iana}} for the value of the capsule type
  Length (i),
  Connection ID Sequence Number (i),
  Virtual Connection ID Sequence Number (i),
  Retire Prior To (i),
  Virtual Connection ID Length (i),
  Virtual Connection ID (8..2040),
  Stateless Reset Token (..),
}
~~~
{: #fig-capsule-new-target-vcid title="New Target VCID Capsule Format"}

Connection ID Sequence Number:
: The sequence number of the target CID registration that the target VCID maps
to ({{cid-registration}}).

Virtual Connection ID Sequence Number:
: The sequence number of the target VCID that the capsule issues
({{vcid-issuance}}).

Retire Prior To:
: The Virtual Connection ID sequence number below which the client is asked to
retire target VCIDs for the same registration ({{vcid-request-retirement}}).
This MUST NOT be greater than the Virtual Connection ID Sequence Number.

Virtual Connection ID Length:
: The length of the target VCID. This MUST be a non-zero, valid connection ID
length for the QUIC version used in the client-to-proxy QUIC connection. The
lengths of the target VCID and target CID SHOULD be equal when possible to
avoid the need to resize packets during replacement.

Virtual Connection ID:
: The proxy-chosen target VCID, whose length is equal to Virtual Connection ID
Length. The client uses it when sending forwarded mode packets, and the proxy
rewrites these packets to contain the correct target CID prior to forwarding
them.

Stateless Reset Token:
: A Stateless Reset Token allowing reset of the client-to-target connection in
response to client-to-target forwarded mode packets. The length of the
Stateless Reset Token is implied by the length of the capsule. Proxies choosing
not to support stateless resets MAY send a zero-length Stateless Reset Token.
Clients receiving a zero-length stateless reset token MUST ignore it.

### NEW_CLIENT_VCID {#capsule-new-client-vcid}

The NEW_CLIENT_VCID capsule is sent by the proxy to propose a client VCID for a
registered client CID. This capsule MUST only be sent by the proxy.

~~~
New Client VCID Capsule {
  Type (i) = see {{iana}} for the value of the capsule type
  Length (i),
  Connection ID Sequence Number (i),
  Virtual Connection ID Sequence Number (i),
  Virtual Connection ID (8..2040),
}
~~~
{: #fig-capsule-new-client-vcid title="New Client VCID Capsule Format"}

Connection ID Sequence Number:
: The sequence number of the client CID registration that the client VCID maps
to ({{cid-registration}}).

Virtual Connection ID Sequence Number:
: The sequence number of the client VCID that the capsule proposes
({{vcid-issuance}}).

Virtual Connection ID:
: The proxy-chosen client VCID that the proxy would use when sending forwarded
mode packets, after rewriting them to contain the client VCID instead of the
client CID. The length of the client VCID is implied by the length of the
capsule. Its length MUST be non-zero and valid for the QUIC version used in
the client-to-proxy QUIC connection, and it is chosen as described in
{{vcids}}. The lengths of the client VCID and client CID SHOULD be equal when
possible to avoid the need to resize packets during replacement.

### ACK_CLIENT_VCID {#capsule-ack-client-vcid}

The ACK_CLIENT_VCID capsule is sent by the client to accept a client VCID
proposed in a NEW_CLIENT_VCID capsule, indicating that the client is ready to
receive forwarded mode packets using it. This capsule MUST only be sent by the
client.

~~~
Acknowledge Client VCID Capsule {
  Type (i) = see {{iana}} for the value of the capsule type
  Length (i),
  Connection ID Sequence Number (i),
  Virtual Connection ID Sequence Number (i),
  Stateless Reset Token (..),
}
~~~
{: #fig-capsule-ack-client-vcid title="Acknowledge Client VCID Capsule Format"}

Connection ID Sequence Number:
: The sequence number of the client CID registration that the client VCID maps
to ({{cid-registration}}).

Virtual Connection ID Sequence Number:
: The sequence number of the client VCID being acknowledged
({{vcid-issuance}}).

Stateless Reset Token:
: A Stateless Reset Token that the client can send in response to
target-to-client forwarded mode packets using the client VCID when it has no
state for that client VCID. The length of the Stateless Reset Token is implied
by the length of the capsule. Clients choosing not to support stateless resets
MAY send a zero-length Stateless Reset Token. Proxies receiving a zero-length
stateless reset token MUST ignore it. Since a client does not send a Stateless
Reset for a client VCID before the proxy retires it ({{vcid-retirement}}), a
proxy that receives a Stateless Reset with this token MUST reset the stream with
H3_DATAGRAM_ERROR error code.

### REJECT_CLIENT_VCID {#capsule-reject-client-vcid}

The REJECT_CLIENT_VCID capsule is sent by the client to refuse a client VCID
proposed in a NEW_CLIENT_VCID capsule. This capsule MUST only be sent by the
client.

~~~
Reject Client VCID Capsule {
  Type (i) = see {{iana}} for the value of the capsule type
  Length (i),
  Reason (i),
  Connection ID Sequence Number (i),
  Virtual Connection ID Sequence Number (i),
}
~~~
{: #fig-capsule-reject-client-vcid title="Reject Client VCID Capsule Format"}

Reason:
: The reason for refusing the client VCID, such as TOO_SHORT or CONFLICT.
See {{iana-cid-reasons}} for the list of reason codes.

Connection ID Sequence Number:
: The sequence number of the client CID registration that the client VCID maps
to ({{cid-registration}}).

Virtual Connection ID Sequence Number:
: The sequence number of the client VCID being refused ({{vcid-issuance}}).

### RETIRE_TARGET_VCID {#capsule-retire-target-vcid}

The RETIRE_TARGET_VCID capsule is sent by the client to indicate that it will
no longer send forwarded mode packets using a target VCID. This capsule MUST
only be sent by the client.

~~~
Retire Target VCID Capsule {
  Type (i) = see {{iana}} for the value of the capsule type
  Length (i),
  Connection ID Sequence Number (i),
  Virtual Connection ID Sequence Number (i),
}
~~~
{: #fig-capsule-retire-target-vcid title="Retire Target VCID Capsule Format"}

Connection ID Sequence Number:
: The sequence number of the target CID registration that the target VCID maps
to ({{cid-registration}}).

Virtual Connection ID Sequence Number:
: The sequence number of the target VCID being retired ({{vcid-issuance}}).

### RETIRE_CLIENT_VCID {#capsule-retire-client-vcid}

The RETIRE_CLIENT_VCID capsule is sent by the proxy to indicate that it will no
longer send forwarded mode packets using a client VCID, or to withdraw a
proposed client VCID. This capsule MUST only be sent by the proxy.

~~~
Retire Client VCID Capsule {
  Type (i) = see {{iana}} for the value of the capsule type
  Length (i),
  Connection ID Sequence Number (i),
  Virtual Connection ID Sequence Number (i),
}
~~~
{: #fig-capsule-retire-client-vcid title="Retire Client VCID Capsule Format"}

Connection ID Sequence Number:
: The sequence number of the client CID registration that the client VCID maps
to ({{cid-registration}}).

Virtual Connection ID Sequence Number:
: The sequence number of the client VCID being retired ({{vcid-issuance}}).

## Issuing Virtual Connection IDs {#vcid-issuance}

After acknowledging a target CID registration, a proxy that is willing to
forward packets for that target CID issues one or more target VCIDs for it using
NEW_TARGET_VCID capsules. The client can use any target VCID that it has
received for sending forwarded mode packets, as long as the target VCID has not
been retired and the proxy has not requested its retirement. Since the proxy is
the endpoint that receives packets using target VCIDs, it MUST be prepared to
receive forwarded mode packets using a target VCID before sending the
NEW_TARGET_VCID capsule that issues it, and the client does not acknowledge
target VCIDs.

After acknowledging a client CID registration, a proxy proposes one or more
client VCIDs for it using NEW_CLIENT_VCID capsules. Unless it has retired the
registration (see below), the client MUST respond to each
with an ACK_CLIENT_VCID capsule if it is prepared to receive forwarded mode
packets using that client VCID, or with a REJECT_CLIENT_VCID capsule otherwise.
A client rejects a client VCID that conflicts with another Connection ID on the
client-to-proxy 4-tuple using the CONFLICT reason code, and a client VCID that
is too short using the TOO_SHORT reason code. The proxy MUST NOT send forwarded
mode packets using a client VCID until it has received an ACK_CLIENT_VCID
capsule for it. After receiving a REJECT_CLIENT_VCID capsule, the proxy can
propose another client VCID, and SHOULD take the reason code into account when
choosing it. If the reason was TOO_SHORT, any client VCID that the proxy
proposes next for the same client CID MUST be longer.

Each NEW_TARGET_VCID and NEW_CLIENT_VCID capsule carries the sequence number of
the Virtual Connection ID that it issues. The first Virtual Connection ID that
the proxy issues for a registration has sequence number 0, and each subsequent
Virtual Connection ID that it issues for the same registration has a sequence
number one greater than the previous one. Capsules refer to a Virtual
Connection ID by the sequence number of its registration and its own sequence
number. A client that receives one of these capsules for a registration that it
has not retired, with a sequence number that is not the next one for that
registration, MUST reset the stream with H3_DATAGRAM_ERROR error code.

Proxies MUST choose unpredictable target VCIDs to avoid forwarding loop attacks,
and MUST use target VCIDs that do not introduce a conflict with any other
Connection ID on the client-to-proxy 4-tuple. Requirements for choosing client
VCIDs are described in {{vcids}}.

A proxy SHOULD keep at least one unused Virtual Connection ID available for each
registered connection ID that it forwards packets for, issuing new ones as
others are retired, within the limit set by the client ({{vcid-limit}}). This
allows the endpoint that sends packets to switch to an unused Virtual Connection
ID without first exchanging capsules, for example when the network path changes
({{migration}}).

A client ignores NEW_TARGET_VCID and NEW_CLIENT_VCID capsules for a
registration that it has already retired, which can happen when the
retirement and issuance capsules are sent simultaneously. These Virtual
Connection IDs are retired along with the others for that registration when the
proxy processes the corresponding RETIRE_CLIENT_CID or RETIRE_TARGET_CID capsule
({{vcid-retirement}}). A client that receives one of these capsules for a
registration that the proxy has not acknowledged MUST reset the stream with
H3_DATAGRAM_ERROR error code.

## Retiring Virtual Connection IDs {#vcid-retirement}

The client retires target VCIDs using RETIRE_TARGET_VCID capsules, and the proxy
retires client VCIDs using RETIRE_CLIENT_VCID capsules. An endpoint retires a
Virtual Connection ID when it will no longer send packets using it, for example
after the network path changes ({{migration}}). An endpoint checks for the
Stateless Reset Token associated with a Virtual Connection ID only after it has
sent packets using that Virtual Connection ID ({{Section 10.3.1 of QUIC}}).
Before sending the capsule that retires a Virtual Connection ID, the endpoint
MUST stop sending forwarded mode packets using it and MUST stop checking for the
associated Stateless Reset Token.

Until a Virtual Connection ID is retired, the endpoint that receives packets
using it MUST keep its state for that Virtual Connection ID, and MUST NOT send a
Stateless Reset in response to packets that use it, since its peer might still
act on the corresponding Stateless Reset Token. Once it has received the capsule
that retires the Virtual Connection ID, it can remove all state for it. Packets
that use a retired Virtual Connection ID and arrive later, for example due to
reordering, can be dropped or answered with a Stateless Reset, which the peer
will ignore.

When a registration is retired, the Virtual Connection IDs associated with it
are retired as well:

- Before sending a RETIRE_TARGET_CID capsule, the client MUST stop using all
  target VCIDs for that target CID and stop checking for their Stateless Reset
  Tokens. These target VCIDs are retired once the proxy receives the capsule.

- After sending a RETIRE_CLIENT_CID capsule, the client continues to accept
  packets using the client VCIDs for that client CID, and MUST NOT send
  Stateless Resets in response to them, until they are retired. Upon receiving
  the RETIRE_CLIENT_CID capsule, the proxy MUST stop using and stop checking for
  the Stateless Reset Tokens of all client VCIDs for that client CID, and retire
  each of them with a RETIRE_CLIENT_VCID capsule.

A proxy can also withdraw a client VCID that it has proposed, before the client
accepts it, by retiring it. A proxy ignores ACK_CLIENT_VCID and
REJECT_CLIENT_VCID capsules for client VCIDs that it has already retired, such
as those that it has withdrawn, and a client ignores RETIRE_CLIENT_VCID capsules
for client VCIDs that are not active, such as those that it has rejected or
ignored. A proxy that receives an ACK_CLIENT_VCID or REJECT_CLIENT_VCID capsule
with a Virtual Connection ID sequence number that it has not yet used for that
registration MUST reset the stream with H3_DATAGRAM_ERROR error code. Likewise,
a client that receives a RETIRE_CLIENT_VCID capsule for a registration that it
has not retired, with a Virtual Connection ID sequence number that the proxy
has not yet used for that registration, MUST reset the stream with
H3_DATAGRAM_ERROR error code.

A proxy that receives a RETIRE_TARGET_VCID capsule for a target VCID that it did
not issue, or that is already retired, MUST reset the stream with
H3_DATAGRAM_ERROR error code.

### Requesting Retirement of Target VCIDs {#vcid-request-retirement}

A proxy might need to stop accepting target VCIDs that it has issued. For
example, a proxy that encodes routing information into target VCIDs using keys
that are periodically rotated, such as described in {{QUIC-LB}}, needs to
replace target VCIDs that were generated with an old key. Much like a QUIC
endpoint does using the Retire Prior To field of the NEW_CONNECTION_ID frame
({{Section 5.1.2 of QUIC}}), the proxy does so by issuing a replacement in a
NEW_TARGET_VCID capsule whose Retire Prior To field asks the client to retire
the target VCIDs that it replaces.

Retire Prior To uses the sequence numbers of target VCIDs ({{vcid-issuance}}). A
client that receives a NEW_TARGET_VCID capsule with a Retire Prior To value
greater than the sequence number of the target VCID in the capsule MUST reset
the stream with H3_DATAGRAM_ERROR error code.

Upon receiving a NEW_TARGET_VCID capsule, the client stops using the target
VCIDs for that target CID that have a sequence number less than the Retire Prior
To value, and MUST retire each of them that it has not already retired, using
RETIRE_TARGET_VCID capsules ({{vcid-retirement}}), before adding the target VCID
that the capsule issues to its set of active target VCIDs. Since the capsule
always issues a target VCID that it does not ask the client to retire, the
client can switch to it without falling back to tunnelled mode.

Retire Prior To replaces target VCIDs, and cannot remove the last target VCID
for a target CID. This document does not define a way for a proxy to stop
accepting forwarded mode packets for a target CID while continuing to proxy the
client-to-target connection. A proxy that is no longer willing to accept
forwarded mode packets from the client, for example due to resource constraints
or a change in policy, closes the request stream.

A proxy does not need to request retirement of client VCIDs, since it is the
endpoint that sends packets using them.

## Limiting Active Virtual Connection IDs {#vcid-limit}

The client limits the number of active Virtual Connection IDs that the proxy
issues for each registered connection ID using the "active-vcid-limit"
parameter of the "Proxy-QUIC-Forwarding" header ({{forwarding-header}}), much
like the active_connection_id_limit transport parameter of QUIC
({{Section 18.2 of QUIC}}). Unlike that transport parameter, the limit applies
to each registered connection ID separately, and only the client sets one, since
the proxy chooses all Virtual Connection IDs.

A Virtual Connection ID counts toward the limit while it is active, whether or
not any packets have been sent using it. A target VCID is active from when the
client receives it until the client retires it. A client VCID is active from
when the client receives it until the client rejects it or receives a
RETIRE_CLIENT_VCID capsule for it. The proxy MUST NOT send a NEW_TARGET_VCID or
NEW_CLIENT_VCID capsule that would cause the number of active Virtual
Connection IDs for a connection ID to exceed the limit.

Since capsules are processed in order, a proxy that has reached the limit can
replace a Virtual Connection ID without waiting for a round trip. For client
VCIDs, it retires one before proposing its replacement. For target VCIDs, it
issues the replacement in a NEW_TARGET_VCID capsule whose Retire Prior To field
asks the client to retire at least one target VCID, which the client does before
adding the new one ({{vcid-request-retirement}}). As in QUIC
({{Section 5.1.1 of QUIC}}), the proxy can therefore issue a target VCID that
temporarily exceeds the limit from its own point of view, until it receives the
corresponding RETIRE_TARGET_VCID capsules.

After processing a NEW_TARGET_VCID or NEW_CLIENT_VCID capsule, including
retiring any target VCIDs that it asks the client to retire, a client that has
more active Virtual Connection IDs for the connection ID than the limit allows
MUST reset the stream with H3_DATAGRAM_ERROR error code.

## Sending With Forwarded Mode

Support for forwarded mode is determined by the "Proxy-QUIC-Forwarding" header,
see {{forwarding-header}}.

Once the client has learned the target server's Connection ID, such as in the
response to a QUIC Initial packet, it can send a REGISTER_TARGET_CID capsule
containing the target CID to request the ability to forward packets.

Forwarded mode requires connection IDs to be registered and Virtual Connection
IDs to be issued, and, as a consequence, cannot be leveraged without a round
trip. This is particularly pronounced when chaining proxies because
registration happens sequentially. While waiting for forwarded mode to become
enabled, clients SHOULD communicate over tunnelled mode to avoid end-to-end
delays.

Prior to receiving the proxy's response, the client MUST send short header
packets tunnelled in HTTP Datagram frames. The client MAY also choose to tunnel
some short header packets even after receiving the successful response.

If the proxy rejects the target CID registration or does not issue any target
VCIDs for it, the client continues to use tunnelled mode for that target CID.

QUIC long header packets MUST NOT be forwarded. These packets can only be
tunnelled within HTTP Datagram frames to avoid exposing unnecessary connection
metadata.

When forwarding, the client sends a QUIC packet with the target VCID
in the QUIC short header, using the same 4-tuple between client and
proxy that was used for the main QUIC connection between client and proxy.

The proxy will forward to the target any short header packets received from
the client that use one of its target VCIDs, after first rewriting the target
VCID to be the correct target CID and executing the negotiated transform.

The proxy MUST only forward non-tunnelled packets from the client that are QUIC
short header packets (based on the Header Form bit), that use target VCIDs that
the proxy has issued and that have not been retired, and that arrive from a
client address from which the proxy accepts forwarded mode packets
({{migration}}).
Packets sent by the client that are forwarded SHOULD be
considered as activity for restarting QUIC's Idle Timeout {{QUIC}}.

When forwarding, the proxy sends a QUIC packet with the client VCID
in the QUIC short header, using the same 4-tuple between client
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

Once the client has acknowledged a client VCID, the proxy SHOULD forward to the
client any short header packets from the target that use the corresponding
client CID, after replacing that client CID with the client VCID and executing
the negotiated transform ({{transforms}}).

Once a client has sent an ACK_CLIENT_VCID capsule to the proxy, it MUST be
prepared to receive forwarded short header packets on the 4-tuple between itself
and the proxy for the specified client VCID, until that client VCID is retired
({{vcid-retirement}}).

The client uses the Destination Connection ID field of the received packet to
determine if the packet was originated by the proxy, or merely forwarded from
the target. The client replaces the client VCID with the real
client CID before processing the packet further.

Clients can cease receiving with forwarded mode over an existing tunnel while
retaining the same client-to-target connection by creating a new tunnel with
"Proxy-QUIC-Forwarding" set to "?0" and migrating the client-to-target connection.

## Packet Transforms {#transforms}

A packet transform is the procedure applied to encode packets as they are sent
on the link between the client and proxy, along with the inverse decode step applied
on receipt. When sending packets, the packet transform is applied after replacing
a CID with a VCID. When receiving packets, the packet transform is applied before
replacing a VCID with a CID.

Simple transforms can be modeled as a function as follows:

Inputs:

1. A QUIC short header packet with a VCID.
1. The mode (encode or decode).
1. The direction (client-to-proxy or proxy-to-client).
1. Any configuration information negotiated at startup.

Output:

* A UDP payload that conforms to the QUIC invariants {{!INVARIANTS=RFC8999}} and does not
  modify the Connection ID.

More complex transform behaviors could have internal state, but no such transforms
are presented here.

Packet transforms are identified by an IANA-registered name, and negotiated in
the HTTP headers (see {{forwarding-header}}).  This document defines two initial
transforms: the `identity` transform and the `scramble` transform.

### The identity transform {#identity-transform}

The `identity` transform does not modify the packet in any way.  When this transform
is in use, a global passive adversary can trivially correlate pairs of packets
that crossed the forwarder, providing a compact proof that a specific client
was communicating to a specific target.

The `identity` transform is identified by the value "identity" {{iana-transforms}}.

Use of this transform is NOT RECOMMENDED if the `scramble` transform is supported
by both the client and the proxy. Implementations MAY choose to not implement or
support the `identity` transform, depending on the use cases and privacy requirements of
the deployment.

### The scramble transform {#scramble-transform}

The `scramble` transform implements length-preserving unauthenticated
re-encryption of QUIC packets while preserving the QUIC invariants.  When
the `scramble` transform is in use, a global passive adversary cannot simply compare the packet
contents on both sides of the proxy
to link the client and target.  However, the `scramble` transform does not defend against
analysis of packet sizes and timing, nor does it protect privacy against an
active attacker. For example, an active attacker that is able to modify packets prior to being
scrambled by the proxy can manipulate the packets in ways that will cause them to be recognizable
(either by interfering with the material that is used for the IV, or by changing sizes or timing
of packets).

Deployments that implement the version of the `scramble` transform defined in this
document MUST use the value "scramble-dt". The finalized version is expected
to use the reserved value "scramble" {{iana-transforms}}.

The `scramble` transform is initialized using a 32-byte random symmetric key.
When offering or selecting this transform, the client and proxy each
generate the key that they will use to encrypt scrambled packets and MUST add it to the
"Proxy-QUIC-Forwarding" header in an `sf-binary` parameter named "scramble-key".
If either side receives a `scramble` transform without the "scramble-key" parameter,
forwarded mode MUST be disabled. Note that each side (client and proxy) generates
its own "scramble-key" that it uses when sending scrambled packets; the value
received in the "scramble-key" parameter is thus used to unscramble packets
received from the peer.

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
   is zero, as required by the QUIC invariants ({{Section 5.2 of INVARIANTS}}).
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

## Connection Maintenance in Forwarded Mode {#maintenance}

When a client and proxy are using forwarded mode, it is possible that there can be
long periods of time in which no ack-eliciting packets
(see {{Section 2 of !QUIC-RETRANSMISSION=RFC9002}}) are exchanged
between the client and proxy. If these periods extend beyond the effective idle
timeout for the client-to-proxy QUIC connection (see {{Section 10.1 of QUIC}}),
the QUIC connection might be closed by the proxy if the proxy does not use
forwarded packets as an explicit liveness signal. To avoid this, clients SHOULD
send keepalive packets to the proxy before the idle timeouts would be reached,
which can be done using a PING frame or another ack-eliciting frame as described
in {{Section 10.1.1 of QUIC}}.

## Handling Connection Migration {#migration}

If a proxy supports QUIC connection migration, it needs to ensure that a migration
event does not end up sending too many tunnelled or forwarded packets on a new
path prior to path validation.

Specifically, the proxy MUST NOT forward packets to an unvalidated client address.
Proxies additionally SHOULD pace the rate at which packets are sent over a new
path to avoid creating unintentional congestion on the new path.

When operating in forwarded mode, the proxy reconfigures forwarding
rules (i.e., the mappings for VCIDs) as the network path between the client and proxy changes.
As with connection IDs in QUIC ({{Section 9.5 of QUIC}}), a Virtual
Connection ID MUST NOT be used for sending packets on more than one network
path, other than when the peer's address changes without its knowledge, such as
due to NAT rebinding. Since the proxy issues more than one Virtual Connection ID
for each connection ID ({{vcid-issuance}}), the client and proxy can switch to a
Virtual Connection ID that they have not used before when the network path
changes, without first exchanging capsules.

Since forwarded mode packets are not authenticated, a proxy only accepts them
from a client address once it has successfully processed a client-to-proxy QUIC
packet from that address, that is, a packet that it decrypted and did not
discard as a duplicate ({{Section 12.3 of QUIC}}), including a probing packet
({{Section 9.1 of QUIC}}). Otherwise, an attacker that has observed a target
VCID could use it to inject packets toward the target from any address
({{active-attacks}}).

The proxy continues to accept forwarded mode packets from an address for as long
as it maintains state for the network path to that address, such as a network
path that the client is probing or the previous network path after a migration
({{Section 9.3.2 of QUIC}}), unless path validation to that address fails. The
proxy drops forwarded mode packets that arrive from any other address.
Regardless of the address that they arrive from, the proxy does not send a
Stateless Reset in response to forwarded mode packets that use a target VCID
that has not been retired ({{vcid-retirement}}).

The proxy sends forwarded mode packets to the client only at the address that
the client-to-proxy QUIC connection uses, and only once that address is
validated. That address only changes when the client-to-proxy QUIC connection
migrates ({{Section 9.3 of QUIC}}), and never in response to forwarded mode
packets. While the client-to-proxy QUIC connection uses an address that it has
not yet validated, the proxy tunnels packets for the client in HTTP Datagram
frames instead, subject to the anti-amplification limit for that address
({{Section 8 of QUIC}}).

### Passive Migration {#passive-migration}

In the event of passive migration, such as NAT rebinding, the client is not
aware that its address has changed, and continues to send packets using the same
Virtual Connection IDs. Until the client sends a client-to-proxy QUIC packet
from its new address, such as a keepalive ({{maintenance}}), forwarded mode
packets are lost in both directions: the proxy drops those that the client sends
from the new address, and continues to send those for the client to its previous
address. Once the proxy receives a client-to-proxy QUIC packet from the new
address, it accepts forwarded mode packets from that address. If that packet
causes the client-to-proxy QUIC connection to migrate to the new address, the
proxy tunnels packets for the client until it has validated the new address,
and then reconfigures its forwarding rules to send forwarded mode packets to the
client at the new address. The Virtual Connection IDs in use do not need to
change, although the proxy MAY switch to an unused client VCID when it
reconfigures its forwarding rules for the new address, and then retire the
client VCID it used before.

A client that has not sent any packets to the proxy for longer than NAT bindings
can be expected to last (see {{Section 3.2 of ?RFC9308}}) might be assigned a
new address by its NAT when it next sends a packet. A client that resumes
sending forwarded mode packets after such a period SHOULD first send an
ack-eliciting packet on the client-to-proxy QUIC connection, such as one
containing a PING frame. This allows the client-to-proxy QUIC connection to
migrate to the new address, and the proxy to accept forwarded mode packets from
it, without waiting for other client-to-proxy QUIC packets.

The steps for passive migration are as follows:

1. Client and proxy exchange connection IDs via capsules, the proxy issues Virtual Connection IDs, and they start using the forwarded mode.
1. The network path experiences NAT rebinding, and packets that the client sends to the proxy arrive from a new address.
1. The proxy drops forwarded mode packets from the new address until it receives a client-to-proxy QUIC packet from that address, and then forwards them to the target.
1. The client-to-proxy QUIC connection migrates to the new address, and the proxy starts validating it ({{Section 9.3 of QUIC}}). Until path validation succeeds, the proxy tunnels packets for the client in HTTP Datagram frames.
1. Once path validation succeeds, the proxy reconfigures target-to-client forwarding rules to send forwarded mode packets to the client at the new address.

No capsules are exchanged in response to passive migration, unless the proxy
chooses to switch to an unused client VCID.

### Active Migration {#active-migration}

In the event of active migration, the client SHOULD probe the new network path
({{Section 9.1 of QUIC}}) before sending forwarded mode packets on it, and
continues to send forwarded mode packets on the previous network path in the
meantime. Once its path validation succeeds, the client knows that the proxy has
received its probe from the new address, and therefore accepts forwarded mode
packets from it. The client then migrates the client-to-proxy QUIC connection to
the new network path by sending a non-probing packet on it
({{Section 9.2 of QUIC}}), and sends forwarded mode packets on it using target
VCIDs that it has not used before. Once the client no longer uses the previous
network path, it retires the target VCIDs that it used on that path
({{vcid-retirement}}).

A proxy that receives a probing packet from a new client address SHOULD initiate
path validation ({{Section 8.2 of QUIC}}) to that address, even before the
client migrates to it, so that it can send forwarded mode packets to the client
on the new network path as soon as the client migrates.

A client that migrates without first probing the new network path, such as when
the previous network path is no longer usable, sends a client-to-proxy QUIC
packet on the new network path before sending forwarded mode packets on it,
since the proxy drops forwarded mode packets that arrive from the new address
before it has processed such a packet.

In active migration, the client also switches to a new connection ID on the
client-to-proxy QUIC connection ({{Section 9.5 of QUIC}}). Once the
client-to-proxy QUIC connection has migrated to the new network path with a new
connection ID and the proxy has validated the path, the proxy MUST use a client
VCID that it has not used on another network path to send forwarded mode
packets on it. After switching to the new network path, the proxy can retire the
client VCIDs that it used on the previous path at any time. Keeping them, for
example until the client retires the target VCIDs that it used on that path,
allows the proxy to use them again if the client returns to that path, instead
of proposing new client VCIDs. However, client VCIDs that have not been retired
count toward the client's limit ({{vcid-limit}}).

If the client has no unused target VCID when it migrates, it sends packets in
tunnelled mode until the proxy issues a new one. Similarly, if the proxy has no
unused client VCID that the client has acknowledged, it sends packets to the
client in tunnelled mode until the client acknowledges a new one. A client that
returns to a previous network path MAY use a target VCID that it used on that
path before, if it has not retired it. In that case, the proxy MAY likewise use
the client VCID that it used on that path, if it has not retired it; otherwise,
the proxy uses an unused client VCID.

The steps for active migration are as follows:

1. Client and proxy exchange connection IDs via capsules, the proxy issues Virtual Connection IDs, and they start using the forwarded mode.
1. Client probes a new network path. Once the proxy has received the client's probe, it accepts forwarded mode packets from the new address, and starts validating that address.
1. Once the client's path validation succeeds, the client migrates the client-to-proxy QUIC connection to the new path and sends forwarded mode packets on it using an unused target VCID.
1. Client retires the target VCIDs that it used on the previous path with RETIRE_TARGET_VCID capsules.
1. Once the client-to-proxy QUIC connection has migrated to the new path and the proxy has validated it, the proxy sends forwarded mode packets to the client using an unused client VCID that the client has acknowledged, and, at a time of its choosing, retires the client VCIDs that it used on the previous path with RETIRE_CLIENT_VCID capsules.
1. Proxy issues new target VCIDs and proposes new client VCIDs to replace those that were retired.

## Handling Server Preferred Addresses {#preferred-address}

QUIC allows servers to tell clients about a preferred address the server
would like to use ({{Section 9.6 of QUIC}}). When this happens, the client can migrate to the preferred
address.

When a client using a proxy wants to migrate to the preferred address of the
target server, it needs to create a new UDP proxying request to the proxy (using
the method defined in {{CONNECT-UDP}}) and using the preferred IP address of the
target as the host to which to connect. This is the behavior clients using a proxy will have regardless of using
the QUIC-aware mechanisms defined in this document. From the proxy's perspective,
the migrating request is separate from the original request.

Note that clients can be aware of the target address being used for the original
proxy request by looking at `next-hop` parameter on a `Proxy-Status` header
sent by the proxy in its response ({{Section 2.1.2 of ?RFC9209}}). This allows
a client to know if it ought to migrate to the preferred address, or is already
connected to the preferred address. To support the ability of clients to do this, proxies
implementing this specification SHOULD send the `Proxy-Status` header in responses
and include the `next-hop` parameter.

## Handling ECN Marking {#ecn}

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

Forwarding ECN markings introduces certain active attacks. See
{{active-attacks}} for more detail.

## Stateless Resets for Forwarded Mode QUIC Packets {#resets}

While the lifecycle of forwarding rules is bound to the lifecycle of the
client-to-proxy HTTP stream, a peer may not be aware that the stream has
terminated. If the forwarding rules are lost or removed without the peer's
knowledge, the peer may send forwarded mode packets even though the client
or proxy no longer has state for that connection. To allow the client or
proxy to signal this, a Stateless Reset Token can be provided for each Virtual
Connection ID. A Stateless Reset for a target VCID resets the client-to-target
connection, and a Stateless Reset for a client VCID causes the proxy to reset
the request stream ({{capsule-ack-client-vcid}}).

When a Virtual Connection ID is retired intentionally, the procedures in
{{vcid-retirement}} ensure that the peer has stopped checking for the
corresponding Stateless Reset Token before a Stateless Reset can be sent for it,
so that retiring a Virtual Connection ID never has either effect.

Consider a proxy that initiates closure of a client-to-proxy QUIC connection.
If the client is temporarily unresponsive or unreachable, the proxy might have
considered the connection closed and removed all connection state (including
the stream mappings used for forwarding). If the client never learned about the closure, it
might send forwarded mode packets to the proxy, assuming the stream mappings
and client-to-proxy connection are still intact. The proxy will receive these
forwarded mode packets, but won't have any state corresponding to the
destination connection ID in the packet. If the proxy has provided a stateless
reset token for the target VCID, it can send a stateless reset
packet to quickly notify the client that the client-to-target connection is
broken.

Stateless Resets sent by the target do not contain a negotiated connection ID,
so the proxy sends them to the client as tunnelled datagrams
({{target-resets}}), even when forwarded mode is enabled.

# Example Exchange

Consider a client that is establishing a new QUIC connection through the proxy.
In this example, the client prefers the `scramble` transform, but also offers the `identity`
transform. It has selected a client CID of `0x31323334`. In order to inform a proxy
of the new QUIC client CID, the client also sends a
REGISTER_CLIENT_CID capsule.

The client will also send the initial QUIC packet with the Long Header form in
an HTTP datagram.

~~~
Client                                              Proxy

STREAM(44): HEADERS             -------->
  :method = CONNECT
  :protocol = connect-udp
  :scheme = https
  :path = /target.example.com/443/
  :authority = proxy.example.org
  proxy-quic-port-sharing = ?1
  proxy-quic-forwarding = ?1; \
      accept-transform="scramble-dt,identity"; \
      scramble-key=:abc...789=:
  capsule-protocol = ?1

STREAM(44): DATA                -------->
  Capsule Type = REGISTER_CLIENT_CID
  Connection ID Sequence Number = 0
  Connection ID = 0x31323334

DATAGRAM                        -------->
  Quarter Stream ID = 11
  Context ID = 0
  Payload = Encapsulated QUIC initial

           <--------  STREAM(44): HEADERS
                        :status = 200
                        proxy-quic-port-sharing = ?1
                        proxy-quic-forwarding = ?1; \
                            transform="scramble-dt"; \
                            scramble-key=:ABC...321=:
                        capsule-protocol = ?1

           <--------  STREAM(44): DATA
                        Capsule Type = ACK_CLIENT_CID
                        Connection ID Sequence Number = 0

                        Capsule Type = NEW_CLIENT_VCID
                        Connection ID Sequence Number = 0
                        Virtual Connection ID Sequence Number = 0
                        Virtual Connection ID = 0x62646668

                        Capsule Type = NEW_CLIENT_VCID
                        Connection ID Sequence Number = 0
                        Virtual Connection ID Sequence Number = 1
                        Virtual Connection ID = 0x7a797877
~~~

The proxy has acknowledged the client CID and proposed two client VCIDs.
Even if there were Short Header packets to send, the proxy
cannot send forwarded mode packets because the client hasn't acknowledged the
client VCIDs.

~~~
STREAM(44): DATA                -------->
  Capsule Type = ACK_CLIENT_VCID
  Connection ID Sequence Number = 0
  Virtual Connection ID Sequence Number = 0
  Stateless Reset Token = Token

  Capsule Type = ACK_CLIENT_VCID
  Connection ID Sequence Number = 0
  Virtual Connection ID Sequence Number = 1
  Stateless Reset Token = Token
~~~

The client acknowledges both client VCIDs. The proxy still
doesn't have any Short Header Packets to send, but, if it did, it would be able
to send with forwarded mode using one of them, keeping the other unused in case
the network path changes.

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

The client may receive forwarded mode packets from the proxy with a client
VCID of 0x62646668 which it will replace with the real client CID
of 0x31323334. All forwarded mode packets sent by the proxy
will have been modified to contain the client VCID instead
of the client CID, and processed by the negotiated `scramble`
packet transform. However, in the unlikely event that a forwarded packet
arrives before the proxy's HTTP response, the client will not know which
transform the proxy selected. In this case, the client will have to ignore
the packet or buffer it until the HTTP response is received.

Once the client learns which Connection ID has been selected by the target
server, it can register it with the proxy to establish a mapping for
forwarding. In this case, that ID is 0x61626364. The client sends the
following capsule:

~~~
STREAM(44): DATA                -------->
  Capsule Type = REGISTER_TARGET_CID
  Connection ID Sequence Number = 0
  Connection ID = 0x61626364
  Stateless Reset Token = Token

           <--------  STREAM(44): DATA
                        Capsule Type = ACK_TARGET_CID
                        Connection ID Sequence Number = 0

                        Capsule Type = NEW_TARGET_VCID
                        Connection ID Sequence Number = 0
                        Virtual Connection ID Sequence Number = 0
                        Retire Prior To = 0
                        Virtual Connection ID = 0x123412341234
                        Stateless Reset Token = Token

                        Capsule Type = NEW_TARGET_VCID
                        Connection ID Sequence Number = 0
                        Virtual Connection ID Sequence Number = 1
                        Retire Prior To = 0
                        Virtual Connection ID = 0x567856785678
                        Stateless Reset Token = Token

/* Client -> Target QUIC short header packets may use forwarded mode */

UDP Datagram                     -------->
  Payload = Forwarded QUIC SH packet

~~~

Upon receiving the NEW_TARGET_VCID capsules, the client starts sending Short Header
packets with a Destination Connection ID of 0x123412341234 directly to the proxy
(not tunnelled), and keeps 0x567856785678 unused in case the network path
changes. These packets are rewritten by the proxy to have the Destination
Connection ID 0x61626364 prior to being forwarded directly to the target. In the
reverse direction, Short Header packets from the target with a Destination
Connection ID of 0x31323334 are modified to replace the Destination Connection
ID with the client VCID of 0x62646668 and forwarded directly to
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

Once a proxied QUIC connection moves into forwarded mode, the client SHOULD
initiate Path MTU discovery to increase its end-to-end MTU. Since each network
path can support a different packet size, the client does so again after it
migrates to a new network path.

Packets that the client sends in tunnelled mode need to fit within HTTP Datagram
frames, so a client that increased the maximum datagram size of the
client-to-target connection while using forwarded mode needs to reduce it when
falling back to tunnelled mode, such as when it starts using a target CID for
which the proxy has not issued target VCIDs, or when it migrates without an
unused target VCID ({{migration}}).

Target-to-client packets can also become too large to tunnel. A target that
validated a larger path MTU while its packets were forwarded continues to send
packets of that size when the proxy tunnels them instead, such as while the
proxy validates a new client address ({{migration}}). Since the target is not
aware of changes to the network path between the client and proxy, it also does
not reduce its maximum datagram size when the client migrates, even though the
new network path might not support packets of the same size. A proxy that cannot
fit a target-to-client packet in an HTTP Datagram frame handles it as described
in {{Section 6.1 of CONNECT-UDP}}, which recommends dropping the packet and
sending an ICMP Packet Too Big message to the target.

Since targets might not act on ICMP messages, a client that wants to avoid
losing target-to-client packets in these cases can use the max_udp_payload_size
transport parameter ({{Section 18.2 of QUIC}}) to limit the target to packets
that fit in an HTTP Datagram frame on the client-to-proxy QUIC connection, at
the cost of the larger packets that forwarded mode could otherwise allow.

# QUIC Version Invariance {#invariance}

QUIC proxies only need to understand the Header Form bit, and the connection ID
fields from packets in client-to-target QUIC connections. Since these fields
are all invariant across future QUIC versions {{INVARIANTS}}, QUIC proxies can
proxy all versions of QUIC.

While QUIC proxies can proxy all versions of QUIC, some optional capabilities
are limited to certain versions. Specifically, some of the
capsules in {{capsule-types-formats}} and {{vcid-capsule-types-formats}}
include a Stateless Reset Token field.
This field is defined in {{QUIC}} and not part of
{{INVARIANTS}}. If a future QUIC version removes or changes the
behavior of Stateless Reset Tokens, the Stateless Reset Token field in each
capsule MUST have a length of zero.

When forwarding mode is enabled, the client and target MAY negotiate any QUIC
version, and MAY send packets of that version through the forwarding path.
The proxy does not know what version they are using, so it can only require that
these packets conform to the QUIC invariants for short-header packets
({{Section 5.2 of INVARIANTS}}).

QUIC version 1 specifies a Fixed Bit (a.k.a. the "QUIC bit") with a fixed value
to support sharing a 5-tuple with other protocols such as DTLS, but the QUIC
invariants do not guarantee the value of this bit.  Accordingly proxies with
forwarding mode enabled MUST NOT rely on this bit for protocol identification,
and SHOULD send and accept the `grease_quic_bit` transport parameter
{{?QUIC-GREASE=RFC9287}} to avoid ossification of the forwarding mode path.

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
(see {{scramble-transform}}).

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

## Active Attacks {#active-attacks}

An active attacker is an adversary that can inject, modify, drop, and view
packets in the network. Some active attacks have different effects between
forwarded mode and tunnelled mode, but active attacks can be used to correlate
flows in either mode.

Both tunnelled mode and forwarded mode (regardless of packet transform) are
vulnerable to packet injection in the target-to-client direction. An attacker
can inject a burst of packets with a known QUIC Connection ID and see which
Connection ID is used for the corresponding burst on the proxy-to-client network path.

Forwarded mode is vulnerable to some active attacks that tunnelled mode is not.
For example, packet injection with a known QUIC Connection ID can also happen in the
client-to-proxy direction, which only affects forwarded mode since
tunnelled mode sends packets within an authenticated and integrity protected
QUIC connection to the proxy (see {{?RFC9001}}). None of the packet transforms
defined in this document provide integrity protection. Even if a packet
transform did provide integrity protection, attackers can inject replayed
packets. Protection against replayed packets is similarly provided by QUIC in
tunnelled mode, but not provided by any of the forwarded mode packet transforms
defined in this document. Similarly, Forwarded mode packets are vulnerable to
active attacks when {{ECN}} markings are forwarded. Specifically, an
attacker could embed a signal over a series of packets by clearing or setting
ECN bits. This attack is possible without injecting, dropping, or modifying the
QUIC packet, but instead modifying the packet's IP header.

An active attacker can modify packets in the client-to-proxy direction, which
would cause a tunnelling proxy to silently drop packets, while a forwarding proxy
would forward the packets. In this way, forwarded mode is less vulnerable to
flow recognition based on corrupting a portion of packets in a burst.

## Connection ID Registration Attacks {#registration-attacks}

Chaining of proxies using forwarded mode introduces the risk of forwarding loop
attacks. Proxies are known to be vulnerable to one such forwarding loop attack
when sharing an IP address and port with other proxies, supporting target-facing
port sharing, and proxying to other proxies. Preventing client VCID conflicts
across proxies sharing an IP address and port mitigates one such forwarding loop
attack. Conflicts can be avoided by partitioning the client VCID space
across proxies, using sufficiently long and random values, or by other means.

[comment1]: # OPEN ISSUE: Figure out how clients and proxies could interact to
[comment2]: # learn whether an adversary is injecting malicious forwarded
[comment3]: # packets to induce rate limiting.

# IANA Considerations {#iana}

## HTTP Header Fields {#iana-header}

This document registers the "Proxy-QUIC-Forwarding" and "Proxy-QUIC-Port-Sharing" header fields in the
"Hypertext Transfer Protocol (HTTP) Field Name Registry"
<[](https://www.iana.org/assignments/http-fields)>.

~~~
    +-------------------------+-----------+-----------------+---------------+----------+
    |      Field Name         |  Status   | Structured Type |   Reference   | Comments |
    +-------------------------+-----------+-----------------+---------------+----------+
    | Proxy-QUIC-Forwarding   | permanent |      Item       | This document |   None   |
    | Proxy-QUIC-Port-Sharing | permanent |      Item       | This document |   None   |
    +-------------------------+-----------+-----------------+---------------+----------+
~~~
{: #iana-header-type-table title="Registered HTTP Header Fields"}

## Proxy QUIC Forwarding Parameter Names

This document establishes a new registry, "Proxy QUIC Forwarding Parameter Names",
for parameter names to use with the "Proxy-QUIC-Forwarding" header field,
in <[](https://www.iana.org/assignments/masque/masque.xhtml)>.
Registrations in this registry are assigned using the
Specification Required policy ({{Section 4.6 of !IANA-POLICY=RFC8126}}).

| Parameter Name    | Description                         | Reference     | Notes                  |
|:------------------|:------------------------------------|:--------------|------------------------|
| accept-transform  | contains supported transforms       | This document | {{forwarding-header}}  |
| transform         | indicates selected transforms       | This document | {{forwarding-header}}  |
| scramble-key      | contains key for scramble transform | This document | {{scramble-transform}} |
| active-vcid-limit | limits active VCIDs per CID         | This document | {{vcid-limit}}         |
{: #iana-parameter-names-table title="Initial Proxy QUIC Forwarding Parameter Names"}

## Packet Transform Names {#iana-transforms}

This document establishes a new registry for packet transform names
in <[](https://www.iana.org/assignments/masque/masque.xhtml)>
and defines two initial transforms: "identity" and "scramble".
Until the `scramble` transform is finalized, deployments use the value
"scramble-dt" instead of the reserved value "scramble" (see {{scramble-transform}}).
Registrations in this registry are assigned using the
Specification Required policy ({{Section 4.6 of IANA-POLICY}}).

| Transform Name | Description       | Specification | Notes                          |
|:---------------|:------------------|:--------------|--------------------------------|
| identity       | no transformation | This Document | {{identity-transform}}     |
| scramble       | Reserved (will be used for final version)  | This Document | {{scramble-transform}} |
{: #iana-packet-transforms-table title="Initial Packet Transform Names"}

## CID Capsule Reason Codes {#iana-cid-reasons}

This document establishes a new registry, "CID Capsule Reason Codes",
for reason codes used in REJECT_CLIENT_CID, REJECT_TARGET_CID, and
REJECT_CLIENT_VCID capsules,
in <[](https://www.iana.org/assignments/masque/masque.xhtml)>.
This registry governs a 62-bit space and operates under the QUIC
registration policy documented in {{Section 22.1 of QUIC}}. This new registry
includes the common set of fields listed in {{Section 22.1.1 of QUIC}}. In
addition to those common fields, all registrations in this registry MUST include
a "Name" field that contains a short name or label for the Reason.

Permanent registrations in this registry are assigned using the Specification
Required policy ({{Section 4.6 of IANA-POLICY}}), except for values
between 0x00 and 0x3f (in hexadecimal; inclusive), which are assigned using
Standards Action or IESG Approval as defined in {{Sections 4.9 and 4.10 of
IANA-POLICY}}.

| Value | Name       | Description                                      | Specification |
|:------|:-----------|:-------------------------------------------------|:--------------|
| 0x00  | DEFAULT    | No specific reason                               | This Document |
| 0x01  | TOO_SHORT  | CID/VCID rejected for being too short            | This Document |
| 0x02  | CONFLICT   | CID/VCID conflicts with existing mapping         | This Document |
{: #iana-cid-reasons-table title="Initial CID Capsule Reason Codes"}

## Capsule Types {#iana-capsule-types}

This document registers sixteen new values in the "HTTP Capsule Types"
registry established by {{HTTP-CAPSULES}}. Note that the codepoints below
will be replaced with lower values before publication.

| Capsule Type               |   Value   | Specification |
|:---------------------------|:----------|:--------------|
| REGISTER_CLIENT_CID        | 0xffe900  | This Document |
| REGISTER_TARGET_CID        | 0xffe901  | This Document |
| ACK_CLIENT_CID             | 0xffe902  | This Document |
| ACK_TARGET_CID             | 0xffe903  | This Document |
| REJECT_CLIENT_CID          | 0xffe904  | This Document |
| REJECT_TARGET_CID          | 0xffe905  | This Document |
| RETIRE_CLIENT_CID          | 0xffe906  | This Document |
| RETIRE_TARGET_CID          | 0xffe907  | This Document |
| MAX_CLIENT_CIDS            | 0xffe908  | This Document |
| MAX_TARGET_CIDS            | 0xffe909  | This Document |
| NEW_TARGET_VCID            | 0xffe90a  | This Document |
| NEW_CLIENT_VCID            | 0xffe90b  | This Document |
| ACK_CLIENT_VCID            | 0xffe90c  | This Document |
| REJECT_CLIENT_VCID         | 0xffe90d  | This Document |
| RETIRE_TARGET_VCID         | 0xffe90e  | This Document |
| RETIRE_CLIENT_VCID         | 0xffe90f  | This Document |
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

# Appendix A. Example of a Forwarded Mode QUIC Packet

The following is an example of a QUIC packet that could have been sent by a
client or proxy in Forwarded Mode.

Original QUIC Destination Connection ID

~~~ hex-dump
002e9184cb0022ca7aecf1128c91d809e1b6853f
~~~

Virtual QUIC Destination Connection ID

~~~ hex-dump
0123456789abcdef0123456789abcdef01234567
~~~

Original QUIC Packet Generated for a Peer.

~~~ hex-dump
50002e9184cb0022ca7aecf1128c91d8
09e1b6853f1ba3bed7043a2163202304
8def32f4f8f260c290490413d24ea6
~~~

Forwarded mode packet with the identity transform

~~~ hex-dump
500123456789abcdef0123456789abcd
ef012345671ba3bed7043a2163202304
8def32f4f8f260c290490413d24ea6
~~~

Forwarded mode packet with scramble key `f13a915f96fb8919d9d8655488ffea5778cac8cffbc27cd38c173bcbad955cff`

~~~ hex-dump
320123456789abcdef0123456789abcd
ef012345678ebe6906e16ec5fc90a02c
0109994c3fed03f9d5d88c5f408bb6
~~~

# Acknowledgments {#acknowledgments}
{:numbered="false"}

Thanks to Lucas Pardue, Ryan Hamilton, and Mirja Kühlewind for their inputs
on this document. The scramble transform design came out of the encryption
design team whose members were Antoine Fressancourt, Mirja Kuehlwind, Tiru Reddy,
Ben Schwartz, and the authors of this document. The authors would also like to
thank Martin Duke for identifying a proxy looping vulnerability that influenced
the capsule registration design.

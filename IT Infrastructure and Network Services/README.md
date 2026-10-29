# Network Architecture and IT Infrastructure Portfolio

This portfolio describes **two separate projects**. Project 1 is an enterprise network architecture and security design for a fictional e-commerce company. Project 2 is a set of hands-on IT infrastructure configuration labs. Both used simulated or lab environments, rather than production systems.

## Project 1 — IT Infrastructure and Network Services

### What I did

I designed an on-premises network for a headquarters in Hanoi and three branches in Sapa, Saigon, and Hung Yen. I mapped the topology and traffic flows, separated employee networks from server and public-facing zones, selected architectures for each site, documented protocol configurations, and assessed threats using trust boundaries, attack trees, and a risk table.

### Architecture

- **Headquarters internal network:** a three-tier campus architecture with core, distribution, and access layers. The core provides redundant high-speed connections, the distribution layer connects network segments and applies policy, and the access layer connects users and devices.
- **Headquarters data center and DMZ:** a spine-and-leaf architecture with multiple paths between switches. The DMZ separates public-facing web, mail, and file services from the private network.
- **Branches:** two-tier LAN architectures for the three smaller sites.
- **WAN edge:** two headquarters edge routers are included for connectivity and resilience toward the ISP.

### Protocols and technologies

| Area | Configuration or design choice | Purpose |
| --- | --- | --- |
| Segmentation and resilience | VLANs, Spanning Tree Protocol (STP), Hot Standby Router Protocol (HSRP) | Separate departments and server zones, avoid Layer 2 loops, and provide redundant default gateways. |
| Routing | Open Shortest Path First (OSPF), Border Gateway Protocol (BGP), route redistribution | Route within sites and exchange routes between the internal and simulated external networks. |
| Business services | HTTP, FTP, SMTP, POP3, DNS | Support web, file transfer, email, and name resolution in the network design. |
| Security | Firewall access lists, HTTPS/SMTPS/FTPS, site-to-site VPN, port security, PortFast/BPDU Guard, Dynamic ARP Inspection, DHCP snooping, AAA, SSH, Syslog | Protect traffic and management access, reduce common Layer 2 attacks, and centralize event logging. |

The report includes protocol configuration examples and **proposed security controls**. Recommendations should not be read as verified deployments at every site.

**Skills demonstrated:** enterprise network design, campus and data-center architecture, VLAN planning, routing and redundancy, segmentation, threat modeling, risk assessment, and security-control selection.

## Project 2 — IT Infrastructure Configuration Labs

### What I did

I configured and tested network and server services using Ubuntu, Linux clients, Windows, and Cisco Packet Tracer. The three reports document each step with screenshots and selected verification results.

| Lab | Configuration and evidence |
| --- | --- |
| Ubuntu Server, DHCP and DNS | Installed and configured ISC DHCP Server and DNS, adjusted service and firewall settings, and checked client address assignment and name resolution. |
| Web, mail, directory, and VLANs | Configured Apache and tested a modified web page locally and from a client; configured Postfix SMTP relay and checked delivery of a test email; provisioned a Samba Active Directory domain controller with Kerberos and tested a Windows domain client; configured switch management, SSH, access lists, VLAN ports, an IEEE 802.1Q trunk, router subinterfaces, and connectivity checks. |
| NFS, permissions, and intrusion detection | Exported and mounted NFS shares; created users, groups, department directories, file permissions, POSIX ACLs, and sudo rules; installed Snort, wrote five custom alert rules, validated the configuration, and observed an ICMP alert from a client ping. |

**Protocols and technologies practiced:** DHCP, DNS, HTTP, SMTP, Samba/SMB, Kerberos, VLANs, IEEE 802.1Q, inter-VLAN routing, SSH, NFS, Linux permissions and ACLs, and Snort. The Snort report verifies the ICMP rule; it does not show individual traffic tests for the other four rules.

**Skills demonstrated:** Linux server administration, service configuration and troubleshooting, client/server testing, Windows domain integration, switch and router configuration, identity and access management, shared storage, intrusion detection, and technical documentation.

## Reports

| Project | Report | Format |
| --- | --- | --- |
| 1 | Network design, protocols, traffic flows, threat modeling, and security recommendations | [PDF](Network%20Design%20and%20Security%20Architecture.pdf) |
| 2 | Ubuntu Server, DHCP and DNS | [PDF](Ubuntu%20Server%2C%20DHCP%20and%20DNS.pdf) · [DOCX](Ubuntu%20Server%2C%20DHCP%20and%20DNS.docx) |
| 2 | Web, Mail, Active Directory and VLANs | [PDF](Web%2C%20Mail%2C%20Active%20Directory%20and%20VLANs.pdf) · [DOCX](Web%2C%20Mail%2C%20Active%20Directory%20and%20VLANs.docx) |
| 2 | NFS, Account Permissions and Snort | [PDF](NFS%2C%20Account%20Permissions%20and%20Snort.pdf) · [DOCX](NFS%2C%20Account%20Permissions%20and%20Snort.docx) |

The reports contain lab screenshots, including example IP addresses, accounts, and passwords. These values are part of the documented exercises and should not be reused in a live environment.

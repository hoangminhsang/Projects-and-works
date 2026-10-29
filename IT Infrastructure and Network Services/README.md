# IT Infrastructure and Network Services

This project documents the design and implementation of an on-premises network for a growing e-commerce business with a headquarters and three branches. The reports cover network architecture, core services, identity and access, file sharing, and intrusion detection. Screenshots in the lab reports record the configuration steps and observed results.

## Project contents

| Report | Coverage |
| --- | --- |
| Network design | Branch and headquarters topology, VLANs, redundancy, server zones, traffic flows, threats, and proposed security controls. |
| Ubuntu Server, DHCP and DNS | Ubuntu Server setup, DHCP address allocation, DNS configuration, and client checks. |
| Web, Mail, Active Directory and VLANs | Apache web hosting, Postfix mail relay, Samba domain services, and switch/router VLAN configuration. |
| NFS, Account Permissions and Snort | NFS exports and mounts, Linux users and groups, directory permissions and ACLs, and Snort rules and alert testing. |

The reports are currently kept offline while their screenshots are reviewed for credentials and other personal details.

## What the lab demonstrates

- Network segmentation and routing between VLANs.
- Address assignment and name resolution for clients.
- Web, mail, and directory services on Linux.
- Shared storage and access controls for different user groups.
- Basic intrusion detection using custom Snort rules.

## Evidence and scope

The reports contain configuration screenshots and selected verification output from a lab environment. A successful command or service status shows the result of that step; it does not by itself establish production readiness. The Snort section demonstrates an ICMP alert, while the other custom rules are documented but not individually tested in the report. IP addresses, account names, and passwords shown in screenshots are lab examples and should not be reused in a live environment.

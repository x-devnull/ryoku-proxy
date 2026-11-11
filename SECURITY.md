# Security policy

**Please do not treat this software as an audited VPN or a universal no-leak guarantee.**

The privileged helper has a fixed operation list and writes to fixed root-owned config locations. User-provided bypass entries are validated before being turned into sing-box config or nft syntax. Only the application's nftables table is manipulated; no global `flush ruleset` is performed. Existing firewall service enablement is changed only after explicit confirmation. New enablement is a 120-second trial that disarms on timeout.

**Threat model:** prevent ordinary local software from using unapproved direct outbound Internet destinations after sing-box drops. Excluded domains/IPs, DNS bootstrap and DHCP/IPv6 neighbor discovery are explicitly permitted. Privileged applications with `CAP_NET_ADMIN`/`CAP_NET_RAW`, root users, local kernel modifications or network namespaces outside this host are **not** covered. Domain matches require discoverable names; matching `*.ru` does not force an application to expose DNS or SNI. `routing_mark` is not a cryptographic assertion of the process that generated a packet.

**Do not enable Kill Switch remotely** unless an independent out-of-band recovery console exists. Test with local console access. Emergency commands are in the README. No automatic failover daemon runs if the GUI is closed. Proxy credentials may be saved with mode 0600 when KWallet/Secret Service is unavailable, and the sing-box configuration itself contains them by necessity. Do not paste real credentials into issue reports.

For vulnerability reports, contact [x_devnull](https://github.com/x-devnull) privately through an available verified contact channel. Do not open an issue containing credentials, tokens, device addresses or exploitable unpatched details.

## Optional passwordless local desktop control (ED 1.0)

Local per-user authorization is restricted to the polkit action
`org.ryoku.proxy.manage`, which is annotated with the exact path of the
root-owned `ryoku-proxy-helper`. Only *active and local* sessions of explicitly
granted users are accepted. This does **not** authorize arbitrary executables
or other polkit actions, but any application running as the granted account
can call the restricted root helper, including actions to disable the firewall.
Grant only trusted users. To revoke: `sudo ryoku-proxy-access revoke USERNAME`.
Do not run the GUI as root. Security audit of root helper is required before
public release.

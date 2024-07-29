# Push SSL to Vault 

> PS: 
> when I discovered the ACME DNS project, I found it really great. It minimizes risk by limiting it to the _acme-challenge subdomain. 
>But, then I found out that it has an account for each subdomain, which is also a way to reduce risk. But this is disastrous when you use acme.sh because all of acme.sh's account information is stored in ~/.acme.sh/account.conf.
>I tried using pre-hook to set environment variables before using acme-dns, but I was disappointed to find that pre-hook as a child process, set environment variables that only affect itself and its child.
>By chance, I found some sub-account profiles containing ACME-DNS configuration information. I was curious about this, so I checked dnsapi/dns_acmedns.sh carefully, and I was pleasantly surprised to find that it reads the information from the configuration file of the sub-account.
>Therefore, you only need to set the environment variable on the 1st run when you use ACME DNS, as it is automatically saved to the sub-account config file. If you are not running ACME DNS for the 1st time, you can manually add ACME DNS configuration information to the sub-account.

> You have to ensure the correct path of hook shell and domain in `VAULT_PATHS_FILE`.

## combine 
```shell
python3 acme-dns.py wlms.dev && source ~/.profile && \
acme.sh --issue \
-d wlms.dev \
-d *.wlms.dev \
--keylength ec-256 \
--server google \
--dns dns_acmedns \
--post-hook "/scripts/hook.sh wlms.dev --ecc" 
```


### push ssl to Vault manually 
> double check the domain is main domain at acme.sh 

```shell
hook.sh wlms.dev --ecc
```

### run with acme.sh (automatically)

```shell
acme.sh --issue \
-d wlms.dev \
-d *.wlms.dev \
--keylength ec-256 \
--server google \
--dns dns_acmedns \
--post-hook "/scripts/hook.sh wlms.dev --ecc" 
```

> Then, the certificate will automatic push to your [Vault]("https://developer.hashicorp.com/vault/api-docs" "Vault Docs") when it updated. 

### set ACME DNS environment 

> fill `acme-dns_list.json`

```
python3 acme-dns.py wlms.dev && source ~/.profile
```

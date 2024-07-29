# Push SSL to Vault 


> You have to ensure the correct path of hook shell and domain in `VAULT_PATHS_FILE`.

### Command

```
acme.sh --issue \
-d wlms.dev \
-d *.wlms.dev \
--keylength ec-256 \
--server google \
--dns dns_acmedns \
--post-hook "/scripts/hook.sh wlms.dev --ecc" 
```

> Then, the certificate will automatic push to your [Vault]("https://developer.hashicorp.com/vault/api-docs" "Vault Docs") when it updated. 

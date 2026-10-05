# Deployment

The app runs on one small Ubuntu VM on **Azure** (Azure for Students, Spain Central,
`Standard_B2ats_v2`). It ran on AWS EC2 before that. Nothing in the pipeline is tied to a
provider: any Ubuntu server reachable over SSH works.

```
Internet ──443──▶ Nginx (TLS, headers) ──▶ 127.0.0.1:5000  ┐
Internet ──2222─▶ Docker port mapping ──▶ container :2222  ├─ one container
                                                           ┘  volume: devops-monitor-data
```

## Infrastructure

The VM, network, security group and static IP are described in
[`infra/terraform`](../infra/terraform). The VM was first created by hand with the Azure CLI.
`imports.tf` adopts those resources into Terraform without rebuilding them:

```bash
cd infra/terraform
cp terraform.tfvars.example terraform.tfvars   # fill in subscription ID and SSH public key
az login
terraform init
terraform plan     # should show 8 imports and only small in-place changes (NSG rules)
terraform apply
```

Azure for Students only allows five regions (France Central, Belgium Central, Germany
West Central, Spain Central, Switzerland North). Of those, only Spain Central offered the
B-series sizes to this subscription. `az policy assignment list` shows the allowed list.

### Manual equivalent

```bash
az group create -n devops-es -l spaincentral
az vm create -g devops-es -n devops-vm -l spaincentral --image Ubuntu2404 \
  --size Standard_B2ats_v2 --admin-username azureuser --generate-ssh-keys \
  --public-ip-sku Standard --nsg-rule SSH
az vm open-port -g devops-es -n devops-vm --port 80,443 --priority 1010
az vm open-port -g devops-es -n devops-vm --port 2222 --priority 1020   # honeypot
```

## Point the domain at it

At the registrar (Namecheap → Advanced DNS), set the `A` records for `@` and `www` to the
VM's public IP.

## One-time server setup

SSH in (`ssh -i key azureuser@<ip>`) and run:

```bash
curl -fsSL https://raw.githubusercontent.com/TrevorvaughanDEV/devops-project/main/scripts/setup-server.sh -o setup.sh
sudo bash setup.sh trevorvaughan.dev you@example.com
```

[`scripts/setup-server.sh`](../scripts/setup-server.sh) checks DNS points at the VM. It
then installs Docker, Nginx and Certbot and gets an auto-renewing certificate. It also
installs [`nginx.conf`](nginx.conf), adds 1 GB of swap, enables `ufw` (SSH, HTTP/S and
2222) and turns on unattended security updates. It is safe to re-run, and re-running it is
how a changed `nginx.conf` gets onto the server.

## GitHub secrets and variables

**Settings → Secrets and variables → Actions**

| Secret | What it is |
|---|---|
| `DOCKER_USERNAME` / `DOCKER_PASSWORD` | Docker Hub login (use an access token) |
| `DEPLOY_HOST` | VM public IP. If unset, the deploy job is skipped, not failed |
| `DEPLOY_USER` | `azureuser` on Azure, `ubuntu` on AWS |
| `DEPLOY_SSH_KEY` | Private key for that user |
| `ABUSEIPDB_KEY` | *Optional.* Free key from abuseipdb.com for attacker reputation scores |

| Variable | Default | What it is |
|---|---|---|
| `HONEYPOT_PORT` | `2222` | Public port the honeypot answers on |
| `ADMIN_SSH_PORT` | `22` | Port the deploy job uses for real SSH |

## What a deploy does

1. Pulls the new image tagged with the commit SHA.
2. Records the image currently running and fixes ownership on the data volume.
3. Starts the new container: web on `127.0.0.1:5000` (only Nginx can reach it), honeypot
   on `HONEYPOT_PORT`, capped at 400 MB of memory, with the `devops-monitor-data` volume
   holding the database and the honeypot's SSH host keys.
4. Polls `/healthz` for up to a minute. If it never passes, the new container is removed,
   the previous image is started again, and the workflow fails.

## Optional: put the honeypot on port 22

Most bots only try port 22, so moving real SSH out of the way multiplies the data. Order
matters, so you can't lock yourself out:

1. Open the new admin port first: `az vm open-port -g devops-es -n devops-vm --port 22022 --priority 1030`
   and `sudo ufw allow 22022/tcp` on the VM.
2. On the VM, add `Port 22022` to `/etc/ssh/sshd_config` (keep `Port 22` for now), then run
   `sudo systemctl restart ssh`. Ubuntu 24.04 uses socket activation, so also run
   `sudo systemctl daemon-reload && sudo systemctl restart ssh.socket`.
3. From your PC, check `ssh -p 22022 azureuser@<ip>` works.
4. Remove `Port 22` from `sshd_config` and restart ssh again.
5. Set the GitHub variables `ADMIN_SSH_PORT=22022` and `HONEYPOT_PORT=22`, then re-run
   the deploy.

## Deploying by hand

If GitHub Actions is slow or down, deploy straight from the server with
[`scripts/deploy.sh`](../scripts/deploy.sh). It does the same build, health check and
automatic rollback as the pipeline:

```bash
curl -fsSL https://raw.githubusercontent.com/TrevorvaughanDEV/devops-project/main/scripts/deploy.sh -o ~/deploy && chmod +x ~/deploy
./deploy
```

Optional settings such as `ABUSEIPDB_KEY=...` go in `~/.whos-knocking.env`.

## Backups

```bash
sudo docker run --rm -v devops-monitor-data:/data -v "$PWD":/backup alpine \
  cp /data/attacks.db /backup/attacks-$(date +%F).db
```

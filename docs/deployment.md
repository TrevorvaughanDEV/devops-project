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

## Turn on auto-deploy

After the one-time setup, run this once on the server:

```bash
curl -fsSL https://raw.githubusercontent.com/TrevorvaughanDEV/devops-project/main/scripts/install-autodeploy.sh | bash
```

It installs `~/deploy` and `~/autodeploy` and a systemd timer that checks `main` every two
minutes. From then on, anything merged to `main` goes live by itself.

| | |
|---|---|
| Deploy now | `~/deploy` (or `~/deploy some-branch` to try a branch) |
| Is it running? | `systemctl list-timers whos-knocking-autodeploy` |
| What happened? | `journalctl -u whos-knocking-autodeploy -n 50` |
| Pause it | `sudo systemctl stop whos-knocking-autodeploy.timer` |

## What a deploy does

1. Fetches the commit and runs the backend lint and tests in the Docker `test` stage. If
   they fail, nothing changes.
2. Builds the image and fixes ownership on the data volume.
3. Starts the new container: web on `127.0.0.1:5000` (only Nginx can reach it), honeypot
   on 2222, capped at 400 MB of memory, with the `devops-monitor-data` volume holding the
   database and the honeypot's SSH host keys.
4. Polls `/healthz` for up to a minute. If it never passes, the new container is removed
   and the previous image is started again.
5. Updates the Nginx config if the repo's copy changed (keeping the old one if
   `nginx -t` fails), and removes old images.

A commit that fails is not retried; the next push gets a fresh attempt.

Optional settings go in `~/.whos-knocking.env`, one per line. For example,
`ABUSEIPDB_KEY=...` turns on attacker reputation scores.

## GitHub secrets

CI only needs `DOCKER_USERNAME` and `DOCKER_PASSWORD` (a Docker Hub access token) to publish
the image. The old `DEPLOY_*` secrets are no longer used and can be deleted.

## The second site

[monitor.trevorvaughan.dev](https://monitor.trevorvaughan.dev) runs the v1 Flask dashboard,
pinned to its last image, as a separate container (`devops-monitor-v1`, `127.0.0.1:5001`)
with its own Nginx site and certificate. Deploys of the main site don't touch it.

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
5. Add `export HONEYPOT_PORT=22` to `~/.bashrc` and to the systemd service
   (`sudo systemctl edit whos-knocking-autodeploy`, then add `Environment=HONEYPOT_PORT=22`
   under `[Service]`), open port 22 to the world in the NSG, and run `~/deploy`.

## Backups

```bash
sudo docker run --rm -v devops-monitor-data:/data -v "$PWD":/backup alpine \
  cp /data/attacks.db /backup/attacks-$(date +%F).db
```

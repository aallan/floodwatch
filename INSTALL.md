# Deployment

## Local (recommended for development)

```bash
python serve.py
```

No dependencies beyond Python 3 standard library (for the server). `fetch_data.py` also only uses the standard library.

The frontend loads Leaflet, Chart.js, and PapaParse from CDNs.

## Digital Ocean App Platform (Recommended)

The simplest deployment option. App Platform serves the static site directly — no server management, no SSH, automatic SSL. The Refresh button works entirely client-side (fetching directly from the EA API in the browser), so no backend service is needed.

### 1. Push to GitHub

Create a repo and push your code including the data files.

Seed the data if you haven't already:

```bash
cd /path/to/floodwatch
python fetch_data.py
```

Initialise the repo and push:

```bash
git init
git add .
git commit -m "Initial commit with seeded data"
git remote add origin git@github.com:YOUR_USERNAME/floodwatch.git
git push -u origin main
```

The CSV data files and GeoJSON overlays are committed to the repo — they're small (~2 MB total) and this means the site works immediately on deploy with full historical data.

### 2. Create the App

**Option A: Via the Dashboard**

- Go to [cloud.digitalocean.com/apps](https://cloud.digitalocean.com/apps)
- Click **Create App**
- Select **GitHub** as the source, authorise access, pick your `floodwatch` repo
- App Platform auto-detects it as a **Static Site** (because of `index.html`)
- Set the region to **London** (closest to Devon)
- Click **Create Resources**

**Option B: Via the CLI**

Install [doctl](https://docs.digitalocean.com/reference/doctl/how-to/install/) and authenticate, then:

```bash
doctl apps create --spec .do/app.yaml
```

### 3. You're Done

App Platform gives you a URL like `https://floodwatch-xxxxx.ondigitalocean.app`. The site is live with:

- Automatic HTTPS/SSL
- Global CDN
- Auto-deploy on every `git push` to `main`

### Adding a Custom Domain

In the App Platform dashboard:

- Go to your app > **Settings** > **Domains**
- Click **Add Domain**, enter your domain name
- Add the CNAME record it gives you to your DNS provider
- SSL is provisioned automatically

### Data Transfer Estimate

Each page load serves the HTML, 19 CSV data files, 7 GeoJSON river overlays, and 4 railway GeoJSON files (2 track + 2 station). CDN libraries (Leaflet, Chart.js, PapaParse) are loaded from external CDNs and don't count towards App Platform transfer.

| Asset | Raw size | Gzipped (approx) |
|-------|----------|-------------------|
| `index.html` | 65 KB | ~15 KB |
| 19 CSV files | 2.7 MB | ~500 KB |
| 7 river GeoJSON files | 245 KB | ~65 KB |
| 4 railway GeoJSON files | 80 KB | ~20 KB |
| **Total per visit** | **~3.1 MB** | **~600 KB** |

App Platform serves static files with gzip compression, so actual transfer is roughly 600 KB per visit. CSV requests include a cache-busting query parameter (`?t=...`) to ensure the browser always fetches fresh data, which means the CDN may not cache CSVs between visits — but at ~500 KB this has negligible impact on transfer.

**Free tier: 1 GiB/month outbound transfer.** That allows approximately **1,700 page loads/month** — around 55 visits/day. For a personal or small-team dashboard this is plenty. If you share the link more widely and exceed the limit, upgrading to a $3/mo static site plan removes the cap.

The hourly GitHub Actions deploys trigger rebuilds on App Platform, but build traffic is internal and not counted as outbound transfer.

### Costs

| Resource | Cost |
|----------|------|
| App Platform (Static Site) | **Free** (up to 3 apps, 1 GiB outbound/mo, ~1,800 visits) |
| Custom domain | ~$10/yr |
| SSL | Free (automatic) |
| GitHub Actions | Free (2,000 mins/mo on free tier, ~1,500 used) |
| EA Flood Monitoring API | Free |
| **Total** | **$0/mo** |

If you exceed the free tier's 1 GiB/month transfer or need more than 3 apps, static site plans start at $3/mo.

## Digital Ocean (LAMP Droplet)

This walks through deploying Floodwatch to a Digital Ocean droplet running Apache and PHP. A $6/mo Regular droplet is more than enough.

### 1. Create the Droplet

- Log in to [cloud.digitalocean.com](https://cloud.digitalocean.com/)
- **Create** > **Droplets**
- **Marketplace** tab > search **LAMP** > select **LAMP on Ubuntu**
- Choose **Regular (Disk type: SSD)** > **$6/mo** (1 GB / 1 CPU)
- Pick a region (London is closest to Devon)
- **Authentication**: SSH key (recommended) or password
- Click **Create Droplet**

Note the droplet's IP address once it's created.

### 2. SSH In and Configure

```bash
ssh root@YOUR_DROPLET_IP
```

On first login the LAMP image may prompt you to set a MySQL password — you can skip this (we don't need a database).

Verify Apache and PHP are running:

```bash
systemctl status apache2
php -v
```

Ensure PHP can make outbound HTTP requests (required for the refresh endpoint):

```bash
php -r "echo ini_get('allow_url_fopen');"
```

This should print `1`.

If it prints empty or `0`, enable it:

```bash
sed -i 's/allow_url_fopen = Off/allow_url_fopen = On/' /etc/php/*/apache2/php.ini
systemctl restart apache2
```

### 3. Deploy the Files

**Option A: From your local machine using rsync**

```bash
rsync -avz --exclude='.server.pid' --exclude='__pycache__' --exclude='.DS_Store' \
  ./ root@YOUR_DROPLET_IP:/var/www/html/floodwatch/
```

**Option B: From your local machine using scp**

```bash
scp -r ./ root@YOUR_DROPLET_IP:/var/www/html/floodwatch/
```

**Option C: Clone from a git repo on the server**

```bash
cd /var/www/html
git clone https://your-repo-url.git floodwatch
```

### 4. Set Permissions

Apache runs as `www-data` and needs to write to the `data/` directory when the Refresh button is clicked:

```bash
chown -R www-data:www-data /var/www/html/floodwatch/data/
chmod -R 775 /var/www/html/floodwatch/data/
```

The rest of the site is static and only needs read access:

```bash
chown root:root /var/www/html/floodwatch/index.html
chown root:root /var/www/html/floodwatch/refresh.php
```

### 5. Seed the Historical Data

If you didn't rsync the `data/` directory with populated CSVs, run the fetcher on the server:

```bash
cd /var/www/html/floodwatch
python3 fetch_data.py
chown -R www-data:www-data data/
```

This downloads up to 2 years of historical data. Takes a few minutes.

### 6. Test It

Open your browser and visit:

```
http://YOUR_DROPLET_IP/floodwatch/
```

You should see the map with stations. Click **Refresh Data** — the activity log should show each station being fetched, and the backend sync should succeed.

Test the refresh endpoint directly:

```bash
curl -X POST http://YOUR_DROPLET_IP/floodwatch/refresh.php
```

Should return JSON with `"success": true` and per-station details.

### 7. Set Up a Custom Domain (Optional)

Point your domain's DNS A record to the droplet IP, then:

```bash
apt install certbot python3-certbot-apache -y
certbot --apache -d yourdomain.com
```

This installs a free Let's Encrypt SSL certificate and configures Apache for HTTPS.

If you want the site at the root of the domain rather than `/floodwatch/`:

```bash
mv /var/www/html/floodwatch/* /var/www/html/
```

Or create an Apache VirtualHost:

```bash
cat > /etc/apache2/sites-available/floodwatch.conf << 'EOF'
<VirtualHost *:80>
    ServerName yourdomain.com
    DocumentRoot /var/www/html/floodwatch

    <Directory /var/www/html/floodwatch>
        AllowOverride None
        Require all granted
    </Directory>

    <Directory /var/www/html/floodwatch/data>
        Options -Indexes
    </Directory>
</VirtualHost>
EOF

a2ensite floodwatch.conf
a2dissite 000-default.conf
systemctl reload apache2
certbot --apache -d yourdomain.com
```

### 8. Set Up Automatic Data Refresh (Optional)

Rather than relying on someone clicking the Refresh button, set up a cron job to keep data fresh:

```bash
crontab -e
```

Add this line to refresh every 15 minutes (matching the EA's measurement interval):

```cron
*/15 * * * * curl -s -X POST http://localhost/floodwatch/refresh.php > /dev/null 2>&1
```

Or if you want to use the Python fetcher for a more thorough periodic sync:

```cron
0 * * * * cd /var/www/html/floodwatch && python3 fetch_data.py --recent > /dev/null 2>&1 && chown -R www-data:www-data data/
```

### 9. Updating the Site

To push changes after local development:

```bash
rsync -avz --exclude='.server.pid' --exclude='__pycache__' --exclude='.DS_Store' --exclude='data/' \
  ./ root@YOUR_DROPLET_IP:/var/www/html/floodwatch/
```

The `--exclude='data/'` flag avoids overwriting the server's live data with your local copy.

### Security Hardening (Recommended)

Disable directory listing on the data folder so people can't browse your CSVs:

```bash
cat > /var/www/html/floodwatch/data/.htaccess << 'EOF'
Options -Indexes
EOF
```

Set up the firewall:

```bash
ufw allow OpenSSH
ufw allow 'Apache Full'
ufw enable
```

Enable automatic security updates:

```bash
apt install unattended-upgrades -y
dpkg-reconfigure -plow unattended-upgrades
```

### Costs

| Resource | Cost |
|----------|------|
| Droplet (Regular, 1GB) | $6/mo |
| Domain (optional) | ~$10/yr |
| SSL (Let's Encrypt) | Free |
| EA Flood Monitoring API | Free |
| **Total** | **$6/mo** |

## Generic LAMP Stack

If you're deploying to an existing LAMP server rather than a fresh Digital Ocean droplet, the key steps are:

1. Upload all files to your web root
2. Ensure `data/` is writable by the web server user (`www-data`, `apache`, or `nginx`)
3. Ensure PHP has `allow_url_fopen = On`
4. Optionally run `python3 fetch_data.py` to seed historical data
5. Optionally set up a cron job to call `refresh.php` periodically

## Keeping Data Fresh

The app automatically detects whether it's running on a backend (LAMP/serve.py) or as a static site (App Platform) and adapts the Refresh button accordingly:

| Deployment | Refresh behaviour |
|------------|-------------------|
| **LAMP / serve.py** | Fetches from EA API client-side, caches to `localStorage`, then POSTs to backend to persist updated CSVs server-side |
| **App Platform (static)** | Fetches from EA API client-side, then caches the last 7 days of refreshed data in `localStorage` so it survives page reloads |

On all deployments, refreshed data is cached to `localStorage` first, so a page reload always shows the latest data you've fetched — even if the browser's HTTP cache serves an older CSV. On App Platform, the initial page load serves the committed CSV data, then merges any cached readings on top.

To keep the committed CSV baseline fresh, the included GitHub Actions workflow runs `fetch_data.py --recent` every hour, commits any new data, and pushes — triggering an automatic redeploy. You can also update manually:

```bash
cd /path/to/floodwatch
python fetch_data.py --recent   # Quick: merge last 2 days
git add data/
git commit -m "Update station data"
git push
```

App Platform auto-deploys on push, so the site will serve the updated CSVs within a minute or two.

### Automating with GitHub Actions

The workflow file `.github/workflows/update-data.yml` updates the CSVs on a schedule:

```yaml
name: Update Station Data

on:
  schedule:
    - cron: '30 * * * *'   # Every hour at :30 past
  workflow_dispatch:        # Manual trigger from Actions tab

jobs:
  update-data:
    runs-on: ubuntu-latest
    permissions:
      contents: write

    steps:
      - name: Checkout repository
        uses: actions/checkout@34e114876b...  # v4.3.1 (SHA-pinned)

      - name: Set up Python
        uses: actions/setup-python@a26af69be...  # v5.6.0 (SHA-pinned)
        with:
          python-version: '3.12'

      - name: Fetch recent data
        run: python fetch_data.py --recent

      - name: Commit and push if changed
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add data/
          if git diff --staged --quiet; then
            echo "No data changes to commit"
          else
            git commit -m "Update station data $(date -u +'%Y-%m-%d %H:%M') UTC"
            git push
          fi
```

This runs at 30 minutes past every hour. EA stations report every 15 minutes but the data takes ~20 minutes to appear on the API, so running at :30 reliably captures each hour's :00 reading. The `--recent` flag fetches only the last 2 days of data and merges it with the existing CSVs, so each run is fast (~30 seconds for all 19 stations) and only commits if data actually changed. Each push triggers an automatic redeploy on App Platform.

You can also trigger the workflow manually from the **Actions** tab in your GitHub repo.

**Free tier fit:** Each `--recent` run typically completes in under 1 minute. At 24 runs/day × 31 days × ~1 minute ≈ **744 minutes/month**, well within the 2,000-minute free tier allowance.

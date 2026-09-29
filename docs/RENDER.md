# FlowerMoon on Render

Runs the existing Transport and browser portal unchanged. This branch adds only
hosting configuration, hosting checks and this guide. No demo mode, sample-data
injection, feature restriction, session timer, credential filter or automatic
project reset is added.

## Create the service

Connect Render to the private `moontolito/FlowerMoon` repository and create a
Blueprint from branch `hosting/render`. Review `render.yaml`: Free web service,
Frankfurt, Docker, port 8000, no persistent disk or database. Automatic deployments
are off. Alternatively, create a Web Service with the same settings and Dockerfile
`deploy/render/Dockerfile`.

Open the assigned HTTPS service URL. The existing FlowerMoon page and **Open
application** button are unchanged. `/app` opens Transport directly.

## Existing API features

The container runs the same application code, public endpoints and dataset as
Codespaces. It restores and verifies the bundled GEM raster during the build.
Map tiles, address search, truck routing, climate, humidity, elevation and other
features keep their current implementations. Their real availability must be
tested from the Render network.

For features requiring credentials, configure the existing variables in Render's
Environment section, for example `FLOWERMOON_ADS_KEY` and, when applicable,
`FLOWERMOON_CLIMATE_API_KEY` / `FLOWERMOON_CLIMATE_URL`. Codespaces secrets are not
automatically copied to Render. Never commit keys or place them in the Docker image.
The existing app passes environment variables to its hosted process normally.

## Hosting behavior

- One service runs one copy of the desktop app, as the existing portal does.
  Visitors share its current project, settings and exported files. This deployment
  does not add independent user accounts or separate desktops.
- Render Free sleeps after 15 minutes without inbound traffic; an open desktop
  connection can keep it active. A new visit wakes it, with a documented delay of
  about one minute.
- Render Free uses temporary local storage. Saved projects, settings, downloads
  and API caches created at runtime are lost on sleep, restart or redeployment.
  This is a platform limitation, not an application reset feature.
- Free compute has 512 MB RAM and 0.1 CPU. The container check exercises that
  allocation. Some data operations may need more resources; passing startup alone
  does not prove every workload fits.

Sources: [Render Free](https://render.com/docs/free),
[Docker deployment](https://render.com/docs/docker).

## Verification

The `Render container` GitHub workflow builds and runs the actual container under
512 MB / 0.1 CPU limits, uses the existing browser checks, probes the actual data
providers from inside the container, and records memory, logs and screenshots.

For a local Docker installation:

```bash
docker build -f deploy/render/Dockerfile -t flowermoon-transport .
docker run --rm --name flowermoon-transport -p 8000:8000 --memory=512m --cpus=0.1 flowermoon-transport
```

Open `http://localhost:8000`. Confirm route calculation, maps, Site & Environment
and Excel export/download. Configure optional credentials through environment
variables or an ignored local environment file when testing those features.

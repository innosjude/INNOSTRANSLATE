# INNOSTRANSLATE — working web app

This release contains a single Flask backend + frontend.

## What works

- Upload MP4/MKV/MOV and common audio files.
- FFmpeg extracts the audio on the server.
- Hugging Face Inference Providers transcribes speech with Whisper.
- Timestamped speech chunks are translated.
- Download the translated SRT subtitle file.
- Download the translated TXT file.
- No Hugging Face token is shown to website visitors.

## What is NOT included yet

AI voice dubbing is intentionally disabled in this release. The UI shows the option, but the server returns a clear message if it is selected instead of pretending a dubbed video was created.

## Deployment on Render

Render supports Python web services and Docker. Create a Web Service from this project/repository.

If using the Docker runtime:
- Dockerfile: already included.
- The container installs FFmpeg.
- The service listens on port 10000.

Add this environment variable in Render:

HF_TOKEN = your Hugging Face token with Inference Providers permission

Optional:
WHISPER_MODEL = openai/whisper-large-v3

Then deploy.

After deployment, open:
https://YOUR-SERVICE-NAME.onrender.com

The same URL serves the INNOSTRANSLATE frontend and its /api/translate backend, so there is no file:// problem.

## Hugging Face token

Create the token in your Hugging Face account and keep it as a server-side secret. Do NOT paste it into index.html and do NOT commit it to GitHub.

## Local testing

Install Docker, then:

docker build -t innostranslate .
docker run --rm -p 10000:10000 -e HF_TOKEN=YOUR_TOKEN innostranslate

Open:
http://localhost:10000

## Important limits

Large videos can take a long time because they must be uploaded, converted to audio, transcribed, and translated. Hosting providers and AI providers can impose their own size, time, rate, and cost limits.


## Why the Hugging Face token is not inside the code

The token is intentionally NOT hardcoded into `index.html` or `app.py`. A public website would expose a token embedded in client-side JavaScript. Instead, the backend reads:

`HF_TOKEN`

from the hosting provider's secret/environment-variable settings. This keeps the credential on the server.

## After deployment

The same backend serves the frontend. That means the browser calls:

`/api/health`
`/api/translate`

on the same HTTPS domain. You do not need to edit the HTML to add a backend URL when frontend and backend are deployed together.

## If you open index.html directly

Do not double-click `index.html` and expect translation to work. A `file:///...` page has no Flask backend behind it. Start the Flask server or deploy the complete project. The previous "Failed to fetch" popup came from exactly this situation.

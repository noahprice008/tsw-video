# TSW video system

Makes and posts two Travel Safety Watch videos a day:
- a main video (25–35 s) at 19:00 Israel time
- a quick video (12–15 s) at 13:00 Israel time

```
n8n (daily)  ->  TSW alerts  ->  Gemini writes the script  ->  automatic checks
             ->  tsw-video renderer (this repo) makes the MP4
             ->  Telegram preview with Stop / Post now
             ->  waits 10 min (tips) or 2 h (timely)  ->  Upload-Post  ->  YouTube, Instagram, Facebook (+ TikTok later)
```

- `template.html`, `render.mjs`, `tts.py`, `audio.py`: the renderer. Voice A (Kokoro `af_heart`), original music, TSW look.
- `server.mjs`: private web service for n8n (`POST /render`, `GET /files/<id>.mp4`), protected by `X-Render-Key`.
- `workflow/TSW_Daily_Videos.json`: the n8n workflow to import.
- `examples/`: sample scripts (`layout_test.json` is invented test data, never publish it).
- `LAUNCH_DATE`: until this date, videos end with "Coming soon to Google Play. Use it free now at travelsafetywatch.com". From this date on, they end with "Get it free on Google Play. Link in bio." Nothing needs re-making.

---

## 1. Put the renderer on the server (one time, about 15 minutes, mostly waiting)

Run these on the VPS (Hostinger terminal or the Hostinger assistant). Replace `<TOKEN>` with the same GitHub token the TSW deploy script uses.

```bash
# get the code
git clone https://<TOKEN>@github.com/noahprice008/tsw-video.git /root/tsw-video

# build it (downloads the voice model once, about 10 minutes)
cd /root/tsw-video && docker build -t tsw-video .

# make a private key for n8n -> renderer (copy the output into your password manager)
openssl rand -hex 24

# find n8n's Docker network (pick the one with n8n in its name)
docker network ls | grep -i n8n

# start it on that network, with the key from above
docker run -d --name tsw-video --restart unless-stopped \
  --network <N8N_NETWORK> \
  -e RENDER_KEY=<KEY_FROM_ABOVE> -e LAUNCH_DATE=2026-11-21 \
  -v tsw-video-data:/data tsw-video

# check it answers
docker run --rm --network <N8N_NETWORK> curlimages/curl -s http://tsw-video:8090/health
# expected: {"ok":true}
```

The renderer has no public address: only n8n can reach it, by the name `tsw-video`.

To update it later: `cd /root/tsw-video && git pull && docker build -t tsw-video . && docker rm -f tsw-video` and run the `docker run` line again.

## 2. Telegram bot (3 minutes)

1. In Telegram, open **@BotFather** and send `/newbot`. Name: `TSW Videos`. Username: anything ending in `bot`, for example `tsw_videos_bot`.
2. Copy the **token** BotFather gives you into your password manager.
3. Open your new bot and send it any message, for example `hi`.
4. In a browser, open `https://api.telegram.org/bot<TOKEN>/getUpdates` and find `"chat":{"id": 123456789`. That number is your **chat ID**.

## 3. n8n (10 minutes)

**Credentials** (n8n → Credentials → Add credential):

| Name | Type | Field name | Value |
|---|---|---|---|
| TSW renderer | Header Auth | `X-Render-Key` | the key from step 1 |
| Upload-Post | Header Auth | `Authorization` | `Apikey ` + your Upload-Post API key (with the space) |
| Pixabay | Query Auth | `key` | your Pixabay API key |
| TSW Telegram bot | Telegram API | Access Token | the BotFather token |
| Gemini | (already there) | | the existing Gemini Header Auth credential |

**Import:** Workflows → Add → Import from file → `TSW_Daily_Videos.json`.

**Connect credentials** (open each node once and pick the credential):
- Gemini: write script → Gemini
- Render video, Download video → TSW renderer
- Pixabay search → Pixabay
- Post to socials → Upload-Post
- all Telegram nodes → TSW Telegram bot

**Settings:** open **Plan today** and replace `PUT_YOUR_CHAT_ID_HERE` with your chat ID.

## 4. Test without posting

1. Open the workflow, click **Execute workflow** and choose the **Quick video 13:00** trigger.
2. About 2 minutes later Telegram shows the video with **Stop** and **Post now**.
3. Tap **Stop**. You get "Stopped. That video was not posted." That proves the whole chain without using any uploads.
4. When you're happy, run it again and tap **Post now** once, to check the post reaches YouTube, Instagram and Facebook.
5. Switch the workflow to **Active**. From then on it runs every day at 13:00 and 19:00.

## Adding TikTok later

After upgrading Upload-Post and connecting TikTok there: open **Post to socials**, duplicate one of the `platform[]` rows and set its value to `tiktok`.

## Daily routine

Nothing, unless you want to look. Each video arrives on Telegram first:
- tips, Did You Know? and stories post 10 minutes later
- timely videos (Before You Fly, Travel Alert, The Week Ahead) post 2 hours later

Tap **Stop** if anything looks wrong. If a script fails the automatic checks (no source, fear words, wrong length), nothing is posted and Telegram tells you why.

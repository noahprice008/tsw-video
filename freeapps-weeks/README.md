# FreeApps weekly video packs

Each file is one week of FreeApps TikTok videos for manual posting. The n8n workflow
"FreeApps: weekly video pack (email only)" reads a file from here, renders every video
(no music, designed cover) on the tsw-video renderer and emails each one to
noah@elevex.digital with its caption and posting time. Nothing is posted automatically.

A file is `{ week, videos: [ { n, app, when, subject, html, spec } ] }`; `spec` is a
`format: "freeapps"` render spec (see freeapps.mjs).

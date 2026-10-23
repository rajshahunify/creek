#!/bin/sh
# creek: join the music stream flowing at __CREEK_HOST__
#   curl -s http://__CREEK_HOST__/join | sh              listen
#   curl -s http://__CREEK_HOST__/join | sh -s install   keep a `creek` command
H="__CREEK_HOST__"

if [ "$1" = "install" ]; then
  mkdir -p "$HOME/.local/bin"
  cat > "$HOME/.local/bin/creek" <<EOF
#!/bin/sh
# creek: join the music stream at $H (re-run the install line if the station moves)
script=\$(curl -fsS "http://$H/join") || { echo "creek: can't reach the stream at $H"; exit 1; }
exec sh -c "\$script" creek "\$@"
EOF
  chmod +x "$HOME/.local/bin/creek"
  echo "installed. type 'creek' to join, 'creek add <link|file|folder>' to add music."
  case ":$PATH:" in
    *":$HOME/.local/bin:"*) ;;
    *) echo "(first add ~/.local/bin to your PATH: echo 'export PATH=\$HOME/.local/bin:\$PATH' >> ~/.bashrc)" ;;
  esac
  exit 0
fi

if command -v python3 >/dev/null 2>&1; then
  code=$(curl -fsS "http://$H/client.py") || { echo "creek: can't reach the stream at $H"; exit 1; }
  if (: </dev/tty) 2>/dev/null; then
    exec python3 -c "$code" "$@" </dev/tty
  fi
  exec python3 -c "$code" "$@" </dev/null
fi

# no python3: plain listening (Ctrl+C leaves)
if [ -n "$1" ]; then echo "creek: '$1' needs python3; plain listening works without it"; exit 1; fi
echo "~ joined the stream at $H (Ctrl+C to leave)"
if command -v ffplay >/dev/null 2>&1; then exec ffplay -nodisp -autoexit -loglevel quiet -probesize 4096 -analyzeduration 0 -fflags nobuffer "http://$H/stream.mp3"
elif command -v mpv >/dev/null 2>&1; then exec mpv --no-video --really-quiet "http://$H/stream.mp3"
elif command -v mpg123 >/dev/null 2>&1; then exec mpg123 -q "http://$H/stream.mp3"
elif command -v pw-play >/dev/null 2>&1; then curl -sN "http://$H/stream.pcm" | pw-play --format s16 --rate 44100 --channels 2 -
elif command -v paplay >/dev/null 2>&1; then curl -sN "http://$H/stream.pcm" | paplay --raw --format=s16le --rate=44100 --channels=2
elif command -v aplay >/dev/null 2>&1; then curl -sN "http://$H/stream.pcm" | aplay -q -t raw -f cd
else echo "creek: no audio player found - install ffmpeg (for ffplay) or mpv"; exit 1
fi

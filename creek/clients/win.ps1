# creek: join the music stream flowing at __CREEK_HOST__
#   irm http://__CREEK_HOST__/win | iex            listen
#   irm http://__CREEK_HOST__/win/install | iex    keep a `creek` command
# Kept pure ASCII on purpose: Windows PowerShell 5.1 can mis-decode downloaded scripts.

$CreekInstall = $false

$CreekUsage = @"
creek                      join the stream (press ? while listening for the keys)
creek --quiet              audio only: no status line, no keys
creek --volume N           start at volume N, 0-100 (default 60)
creek pause | play | next | prev | clear    control the stream for everyone
creek fwd | back [seconds]                 jump ahead / back in this song (5 s), for everyone
creek queue                what's on, what's up next, what played before
creek find <words>         look for a song on the station
creek post <link | number from find>   queue a song (it plays after the songs already waiting)
creek next <link | number from find>   play a song next, ahead of the queue
creek add <link|file|folder> ...   add music to the shuffle
"@

$CreekHelp = @(
    '  keys   a  play a song next (a link, or words to find one)    e  add one to the end of the queue    / find',
    '         space  pause / play    n  next    p  previous    left/right  jump 5 s    l  what''s on & up next',
    '         c  clear the queue     1-6  drop an emoji     +/-  volume    ?  this help    q  leave'
)
$CreekDone = @{ pause = 'paused for everyone'; resume = 'playing'; next = 'next song'; prev = 'previous song' }
$CreekSeen = @{ pause = 'someone paused the stream'; resume = 'someone pressed play'
                next = 'someone skipped ahead'; prev = 'someone went back a song'
                clear = 'someone cleared the up-next queue'
                fwd = '>> someone jumped ahead 5 s'; back = '<< someone jumped back 5 s' }

function Format-CreekCleared($n) {
    $s = 's'
    if ($n -eq 1) { $s = '' }
    return "queue cleared ($n song$s; they stay in the shuffle)"
}

function Invoke-Creek {
    $base = 'http://__CREEK_HOST__'
    $argv = @($args)
    $ProgressPreference = 'SilentlyContinue'
    if ($CreekInstall) { Install-Creek $base; return }
    if ($argv.Count -gt 0 -and $argv[0] -eq 'add') {
        Add-CreekMusic $base @($argv | Select-Object -Skip 1)
        return
    }
    if ($argv.Count -gt 0 -and -not ([string]$argv[0]).StartsWith('-')) {
        Invoke-CreekCommand $base $argv
        return
    }
    $quiet = $false
    $volume = 60
    for ($i = 0; $i -lt $argv.Count; $i++) {
        $a = [string]$argv[$i]
        if ($a -eq '-q' -or $a -eq '--quiet') { $quiet = $true }
        elseif ($a -eq '-v' -or $a -eq '--volume') { $i++; $volume = [Math]::Max(0, [Math]::Min(100, [int]$argv[$i])) }
        else { Write-Host $CreekUsage; return }
    }
    Start-CreekListening $base $volume $quiet
}

function Get-CreekError($err) {
    try { $d = ($err.ErrorDetails.Message | ConvertFrom-Json).detail; if ($d) { return $d } } catch {}
    return "can't reach the stream"
}

function Get-CreekId {
    # anonymous but stable for this person on this PC, so 'one posted song each' means something
    $sha = [System.Security.Cryptography.SHA1]::Create()
    $bytes = $sha.ComputeHash([Text.Encoding]::UTF8.GetBytes("creek|$env:COMPUTERNAME|$env:USERNAME"))
    return (($bytes | ForEach-Object { $_.ToString('x2') }) -join '').Substring(0, 16)
}

function Format-CreekTime($sec) {
    $s = [int]$sec
    return '{0}:{1:00}' -f [Math]::Floor($s / 60), ($s % 60)
}

function Format-CreekQueue($q) {
    $mark = '>'
    if ($q.paused) { $mark = '||' }
    $lines = @("  now      $mark $($q.now)")
    $next = @($q.upnext)
    for ($i = 0; $i -lt $next.Count; $i++) {
        $label = ''
        if ($i -eq 0) { $label = 'up next' }
        $hint = ''
        if ($i -eq 0) { $hint = '      (c clears the queue)' }
        $lines += ('  {0,-8} {1}. {2}{3}' -f $label, ($i + 1), $next[$i], $hint)
    }
    $pick = $q.shuffle_next
    $rest = "the shuffle, $($q.songs) songs"
    if ($next.Count -eq 0) {
        if ($pick) {
            $lines += "  up next  $pick   (the shuffle's pick)"
            $lines += "  then     the rest of $rest"
        } else {
            $lines += '  up next  nothing posted yet, so the shuffle picks'
            $lines += "  then     $rest"
        }
    }
    elseif ($pick) { $lines += "  then     $pick   (the shuffle's pick), then the rest of $rest" }
    else { $lines += "  then     $rest" }
    if (@($q.earlier).Count -gt 0) { $lines += '  earlier  ' + ((@($q.earlier) | Select-Object -First 3) -join '  .  ') }
    return $lines
}

function Invoke-CreekCommand($base, $argv) {
    $cmd = [string]$argv[0]
    $rest = @($argv | Select-Object -Skip 1)
    $id = Get-CreekId
    try {
        if (@('pause', 'play', 'next', 'prev', 'clear') -contains $cmd -and $rest.Count -eq 0) {
            $action = $cmd
            if ($cmd -eq 'play') { $action = 'resume' }
            $r = Invoke-RestMethod -Method Post -Uri "$base/ctl/${action}?id=$id" -UseBasicParsing -TimeoutSec 5
            if ($action -eq 'clear') { Write-Host (Format-CreekCleared $r.cleared) } else { Write-Host $CreekDone[$action] }
        }
        elseif (@('fwd', 'back') -contains $cmd -and $rest.Count -le 1) {
            $by = ''
            if ($rest.Count -eq 1) { $by = "&by=$([int]$rest[0])" }
            $r = Invoke-RestMethod -Method Post -Uri "$base/ctl/${cmd}?id=$id$by" -UseBasicParsing -TimeoutSec 5
            $mark = '>>'
            if ($cmd -eq 'back') { $mark = '<<' }
            Write-Host "$mark $(Format-CreekTime $r.pos) / $(Format-CreekTime $r.dur)"
        }
        elseif ($cmd -eq 'queue') { Format-CreekQueue (Invoke-RestMethod -Uri "$base/queue" -UseBasicParsing) | ForEach-Object { Write-Host $_ } }
        elseif ($cmd -eq 'find' -and $rest.Count -gt 0) {
            $hits = @(Invoke-RestMethod -Uri "$base/search?q=$([Uri]::EscapeDataString($rest -join ' '))" -UseBasicParsing) | ForEach-Object { $_ }
            $hits = @($hits)
            if ($hits.Count -eq 0) { Write-Host 'no songs on the station match that' }
            for ($i = 0; $i -lt $hits.Count; $i++) {
                Write-Host ("  {0}. {1}  ({2})   creek post #{3}" -f ($i + 1), $hits[$i].song, (Format-CreekTime $hits[$i].duration), $hits[$i].id)
            }
        }
        elseif (@('post', 'next') -contains $cmd -and $rest.Count -eq 1) {
            $what = ([string]$rest[0]).TrimStart('#')
            $front = ''
            if ($cmd -eq 'next') { $front = '&next=1' }
            if ($what -match '^\d+$') {
                Write-Host (Invoke-RestMethod -Method Post -Uri "$base/post?track=$what&id=$id$front" -UseBasicParsing).msg
            } else {
                $t = Invoke-RestMethod -Method Post -Uri "$base/post?url=$([Uri]::EscapeDataString($what))&id=$id$front" -UseBasicParsing
                Write-Host -NoNewline 'fetching'
                do {
                    Start-Sleep -Milliseconds 1500
                    $s = Invoke-RestMethod -Uri "$base/add/$($t.ticket)" -UseBasicParsing
                    Write-Host -NoNewline '.'
                } while (@('done', 'failed') -notcontains $s.status)
                Write-Host ''
                Write-Host $s.msg
            }
        }
        else { Write-Host $CreekUsage }
    } catch { Write-Host "creek: $(Get-CreekError $_)" }
}

# --- playing ---------------------------------------------------------------------------------

function New-CreekPlayer($url, $volume) {
    if ($ExecutionContext.SessionState.LanguageMode -eq 'FullLanguage') {
        try {
            $wmp = New-Object -ComObject WMPlayer.OCX -ErrorAction Stop
            $wmp.settings.autoStart = $true
            $wmp.settings.volume = $volume
            try { $wmp.network.bufferingTime = 1000 } catch {}   # WMP buffers 5 s by default: 5 s behind
            return @{ Kind = 'wmp'; Obj = $wmp; Url = $url; Volume = $volume }
        } catch {}
        try {
            Add-Type -AssemblyName PresentationCore -ErrorAction Stop
            $mp = New-Object System.Windows.Media.MediaPlayer
            $mp.Volume = $volume / 100
            return @{ Kind = 'wpf'; Obj = $mp; Url = $url; Volume = $volume }
        } catch {}
    }
    $ff = Get-Command ffplay -ErrorAction SilentlyContinue
    if ($ff) { return @{ Kind = 'ffplay'; Path = $ff.Source; Obj = $null; Url = $url; Volume = $volume } }
    Write-Host "creek: can't play audio here (Windows Media Player is missing or blocked)."
    Write-Host "       Installing ffmpeg (so 'ffplay' is on PATH) fixes it: winget install ffmpeg"
    return $null
}

function Start-CreekPlayer($p) {
    # (re)open the stream: always lands at the live edge
    switch ($p.Kind) {
        'wmp' { $p.Obj.URL = $p.Url; $p.Obj.controls.play() }
        'wpf' { $p.Obj.Close(); $p.Obj.Open([Uri]$p.Url); $p.Obj.Play() }
        'ffplay' {
            if ($p.Obj -and -not $p.Obj.HasExited) { $p.Obj.Kill() }
            $p.Obj = Start-Process $p.Path -WindowStyle Hidden -PassThru -ArgumentList @(
                '-nodisp', '-autoexit', '-loglevel', 'quiet', '-volume', $p.Volume, '-rw_timeout', '15000000',
                '-probesize', '4096', '-analyzeduration', '0', '-fflags', 'nobuffer', '-i', $p.Url)
        }
    }
    $p.Since = [DateTime]::Now
    $p.LastPos = -1
}

function Suspend-CreekPlayer($p) {
    # silence our own speakers at once when we press pause (the station's fade reaches everyone else)
    try {
        switch ($p.Kind) {
            'wmp' { $p.Obj.controls.pause() }
            'wpf' { $p.Obj.Pause() }
            'ffplay' { if ($p.Obj -and -not $p.Obj.HasExited) { $p.Obj.Kill() } }
        }
    } catch {}
}

function Test-CreekPlaying($p) {
    switch ($p.Kind) {
        'wmp' {
            # 3 playing, 6 buffering, 7 waiting, 9 transitioning, 11 reconnecting
            if (@(3, 6, 7, 9, 11) -contains $p.Obj.playState) { return $true }
            $pos = $p.Obj.controls.currentPosition
        }
        'wpf' { $pos = $p.Obj.Position.TotalSeconds }
        'ffplay' { return ($p.Obj -and -not $p.Obj.HasExited) }
    }
    $moving = $pos -ne $p.LastPos
    $p.LastPos = $pos
    return $moving
}

function Set-CreekVolume($p, $delta) {
    $p.Volume = [Math]::Max(0, [Math]::Min(100, $p.Volume + $delta))
    switch ($p.Kind) {
        'wmp' { $p.Obj.settings.volume = $p.Volume }
        'wpf' { $p.Obj.Volume = $p.Volume / 100 }
    }
}

function Stop-CreekPlayer($p) {
    try {
        switch ($p.Kind) {
            'wmp' { $p.Obj.controls.stop(); $p.Obj.close(); [void][Runtime.InteropServices.Marshal]::ReleaseComObject($p.Obj) }
            'wpf' { $p.Obj.Stop(); $p.Obj.Close() }
            'ffplay' { if ($p.Obj -and -not $p.Obj.HasExited) { $p.Obj.Kill() } }
        }
    } catch {}
}

# --- the screen ------------------------------------------------------------------------------

function Get-CreekWidth {
    try { $w = [Console]::WindowWidth } catch { $w = 0 }
    if ($w -lt 20) { $w = 80 }   # some hosts report 0 when they don't know
    return $w
}

function Write-CreekLines($lines) {
    # print above the status line; it redraws underneath on the next frame
    $w = Get-CreekWidth
    [Console]::Write("`r" + (' ' * ($w - 1)) + "`r")
    foreach ($l in @($lines)) {
        $l = [string]$l
        if ($l.Length -gt $w - 1) { $l = $l.Substring(0, $w - 1) }
        Write-Host $l
    }
}

function Read-CreekLine($prompt) {
    # let PowerShell read the line so pasting works; the status line waits meanwhile
    $w = Get-CreekWidth
    [Console]::Write("`r" + (' ' * ($w - 1)) + "`r")
    [Console]::TreatControlCAsInput = $false
    try { [Console]::CursorVisible = $true } catch {}
    $line = Read-Host $prompt
    try { [Console]::CursorVisible = $false } catch {}
    [Console]::TreatControlCAsInput = $true
    try {
        [Console]::SetCursorPosition(0, [Console]::CursorTop - 1)
        [Console]::Write(' ' * ($w - 1))
        [Console]::SetCursorPosition(0, [Console]::CursorTop)
    } catch {}
    return ([string]$line).Trim()
}

function Find-CreekSong($base, $id, $words, $front) {
    # look the words up, list the hits, ask for a number; returns the message to show (or nothing)
    $hits = @(Invoke-RestMethod -Uri "$base/search?q=$([Uri]::EscapeDataString($words))" -UseBasicParsing -TimeoutSec 5) | ForEach-Object { $_ }
    $hits = @($hits)
    if ($hits.Count -eq 0) { return "no songs on the station match '$words' (a takes a link instead)" }
    $lines = @()
    for ($i = 0; $i -lt $hits.Count; $i++) {
        $lines += "  $($i + 1). $($hits[$i].song)  ($(Format-CreekTime $hits[$i].duration))"
    }
    Write-CreekLines $lines
    $what = 'queue'
    if ($front) { $what = 'play next' }
    $pick = Read-CreekLine "number to $what (1-$($hits.Count), Enter on its own cancels)"
    if ($pick -match '^\d+$' -and [int]$pick -ge 1 -and [int]$pick -le $hits.Count) {
        $next = ''
        if ($front) { $next = '&next=1' }
        $r = Invoke-RestMethod -Method Post -UseBasicParsing -TimeoutSec 5 `
            -Uri "$base/post?track=$($hits[[int]$pick - 1].id)&id=$id$next"
        return "~ $($r.msg) ~"
    }
}

# --- listening -------------------------------------------------------------------------------

function Start-CreekListening($base, $volume, $quiet) {
    $p = New-CreekPlayer "$base/stream.mp3" $volume
    if (-not $p) { return }
    try { Add-Type -AssemblyName System.Windows.Forms -ErrorAction Stop; $pump = $true } catch { $pump = $false }

    # Windows Terminal, VS Code and ConEmu draw colour emoji. The classic console window can't (its fonts
    # have none), so there the emoji become the nearest symbols those fonts do have: wave, heart, sparkle,
    # flame, smile, notes. CREEK_EMOJI=1 or 0 overrides the guess.
    $fancy = [bool]($env:WT_SESSION -or $env:TERM_PROGRAM -or $env:ConEmuANSI -eq 'ON')
    if ($env:CREEK_EMOJI) { $fancy = $env:CREEK_EMOJI -ne '0' }
    if ($fancy) {
        $glyphs = @(0x1F30A, 0x1F49B, 0x2728, 0x1F525, 0x1F60C, 0x1F3B6) | ForEach-Object { [char]::ConvertFromUtf32($_) }
    } else {
        $glyphs = @(0x2248, 0x2665, 0x263C, 0x25B2, 0x263A, 0x266B) | ForEach-Object { [string][char]$_ + ' ' }
    }
    $note = [string][char]0x266A
    $water = '~~ ~~~ ~ ~~~~  ~~ ~ ~~~ ~~  ~ ~~~~ ~ '
    $riverWidth = 26
    $id = Get-CreekId
    $since = -1
    $now = $null
    $offline = $false
    $drops = New-Object System.Collections.ArrayList
    $lastPoll = [DateTime]::MinValue
    $quietSince = $null
    $backoff = 15
    $frame = 0
    $flash = '~ a play a song next . e add one to the queue . space pause . ? all keys . q leave ~'
    $flashUntil = [DateTime]::Now.AddSeconds(6)
    $postTicket = $null
    $held = $false                # our player is paused because we pressed pause
    $heldAt = [DateTime]::MinValue
    $mine = @{}                   # notices we caused ourselves
    $lastNotice = $null
    $oldCtrlC = [Console]::TreatControlCAsInput
    $oldEncoding = [Console]::OutputEncoding

    Start-CreekPlayer $p
    try {
        if (-not $quiet) {
            [Console]::TreatControlCAsInput = $true
            try { [Console]::CursorVisible = $false } catch {}
            [Console]::OutputEncoding = [Text.Encoding]::UTF8   # for the emoji, and the symbols that stand in for them
        }
        while ($true) {
            if ($pump) { [System.Windows.Forms.Application]::DoEvents() }
            $t = [DateTime]::Now

            if (-not $quiet) {
                while ([Console]::KeyAvailable) {
                    $k = [Console]::ReadKey($true)
                    $ctrl = ($k.Modifiers -band [ConsoleModifiers]::Control) -ne 0
                    if ($k.Key -eq 'Q' -or ($ctrl -and $k.Key -eq 'C')) { return }
                    $ch = [string]$k.KeyChar
                    if ('123456'.Contains($ch) -and $ch) {
                        try {
                            [void](Invoke-RestMethod -Method Post -Uri "$base/react?e=$([int]$ch - 1)&id=$id" -UseBasicParsing -TimeoutSec 2)
                            $lastPoll = [DateTime]::MinValue
                        } catch {}
                    }
                    elseif ($k.Key -eq 'RightArrow' -or $k.Key -eq 'LeftArrow') {
                        $action = 'fwd'
                        $mark = '>>'
                        if ($k.Key -eq 'LeftArrow') { $action = 'back'; $mark = '<<' }
                        try {
                            $r = Invoke-RestMethod -Method Post -Uri "$base/ctl/${action}?id=$id" -UseBasicParsing -TimeoutSec 3
                            $mine[[string]$r.notice] = $true
                            $flash = "$mark $(Format-CreekTime $r.pos) / $(Format-CreekTime $r.dur)"
                            $flashUntil = $t.AddSeconds(2)
                            $lastPoll = [DateTime]::MinValue
                        } catch { $flash = Get-CreekError $_; $flashUntil = $t.AddSeconds(3) }
                    }
                    elseif ($ch -eq ' ' -or $ch -ceq 'n' -or $ch -ceq 'p') {
                        if ($ch -eq ' ') {
                            $action = 'pause'
                            if ($held -or ($now -and $now.paused)) { $action = 'resume' }
                        }
                        elseif ($ch -ceq 'n') { $action = 'next' }
                        else { $action = 'prev' }
                        try {
                            $r = Invoke-RestMethod -Method Post -Uri "$base/ctl/${action}?id=$id" -UseBasicParsing -TimeoutSec 3
                            $mine[[string]$r.notice] = $true
                            if ($action -eq 'pause') { Suspend-CreekPlayer $p; $held = $true; $heldAt = $t }
                            elseif ($held) { $held = $false; Start-CreekPlayer $p }
                            $flash = $CreekDone[$action]
                            $flashUntil = $t.AddSeconds(2.5)
                            $lastPoll = [DateTime]::MinValue
                        } catch { $flash = Get-CreekError $_; $flashUntil = $t.AddSeconds(3) }
                    }
                    elseif ($ch -eq 'l') {
                        try { Write-CreekLines (Format-CreekQueue (Invoke-RestMethod -Uri "$base/queue" -UseBasicParsing -TimeoutSec 3)) }
                        catch { $flash = Get-CreekError $_; $flashUntil = $t.AddSeconds(3) }
                    }
                    elseif ($ch -eq '?' -or $ch -eq 'h') { Write-CreekLines $CreekHelp }
                    elseif ($ch -eq 'c') {
                        # it empties everyone's queue, so ask first
                        Write-CreekLines @('clear the up-next queue for everyone? (y/n)')
                        $yes = [Console]::ReadKey($true).KeyChar -eq 'y'
                        if ($yes) {
                            try {
                                $r = Invoke-RestMethod -Method Post -Uri "$base/ctl/clear?id=$id" -UseBasicParsing -TimeoutSec 3
                                $mine[[string]$r.notice] = $true
                                $flash = Format-CreekCleared $r.cleared
                            } catch { $flash = Get-CreekError $_ }
                        } else { $flash = '~ never mind ~' }
                        $flashUntil = [DateTime]::Now.AddSeconds(4)
                        $lastPoll = [DateTime]::MinValue
                    }
                    elseif ($ch -eq '+' -or $ch -eq '=') { Set-CreekVolume $p 10 }
                    elseif ($ch -eq '-') { Set-CreekVolume $p -10 }
                    elseif ($ch -eq '/') {
                        $words = Read-CreekLine 'find a song (Enter on its own cancels)'
                        if ($words) {
                            try { $msg = Find-CreekSong $base $id $words $false }
                            catch { $msg = Get-CreekError $_ }
                            if ($msg) { $flash = $msg; $flashUntil = [DateTime]::Now.AddSeconds(5) }
                        }
                    }
                    elseif ($ch -eq 'a' -or $ch -eq 'e') {
                        # a: play next, at the front of the queue. e: the end of the queue. Either takes a link,
                        # or words to find a song on the station
                        $front = $ch -eq 'a'
                        if ($front) { $link = Read-CreekLine 'play next - a link, or words to find a song (Enter on its own cancels)' }
                        else { $link = Read-CreekLine 'add to the end of the queue - a link, or words to find a song (Enter on its own cancels)' }
                        $next = ''
                        if ($front) { $next = '&next=1' }
                        if ($link -and $link -notmatch '^https?://') {
                            try { $msg = Find-CreekSong $base $id $link $front }
                            catch { $msg = Get-CreekError $_ }
                            if ($msg) { $flash = $msg; $flashUntil = [DateTime]::Now.AddSeconds(5) }
                        }
                        elseif ($link -match '^https?://') {
                            try {
                                $r = Invoke-RestMethod -Method Post -UseBasicParsing -TimeoutSec 5 `
                                    -Uri "$base/post?url=$([Uri]::EscapeDataString($link))&id=$id$next"
                                $postTicket = $r.ticket
                                $flash = '~ fetching your song... ~'
                                $flashUntil = [DateTime]::Now.AddMinutes(10)
                            } catch { $flash = Get-CreekError $_; $flashUntil = [DateTime]::Now.AddSeconds(6) }
                        }
                    }
                }

                if (($t - $lastPoll).TotalSeconds -ge 1) {
                    $lastPoll = $t
                    try {
                        $now = Invoke-RestMethod -Uri "$base/now?since=$since" -UseBasicParsing -TimeoutSec 2
                        foreach ($r in $now.reactions) { [void]$drops.Add(@{ Pos = 0; Glyph = $glyphs[$r] }) }
                        $since = $now.seq
                        $n = @($now.notice)
                        if ($null -ne $lastNotice -and $n[0] -gt $lastNotice -and -not $mine[[string]$n[0]]) {
                            $flash = $CreekSeen[[string]$n[1]]
                            $flashUntil = [DateTime]::Now.AddSeconds(3)
                        }
                        $lastNotice = $n[0]
                        if ($held -and -not $now.paused -and ($t - $heldAt).TotalSeconds -gt 2) {
                            $held = $false                # someone else pressed play (or next)
                            Start-CreekPlayer $p
                        }
                        if ($offline) { $offline = $false; Start-CreekPlayer $p }
                    } catch { $offline = $true }
                    if ($postTicket) {
                        try {
                            $s = Invoke-RestMethod -Uri "$base/add/$postTicket" -UseBasicParsing -TimeoutSec 2
                            if (@('done', 'failed') -contains $s.status) {
                                $flash = "~ $($s.msg) ~"
                                $flashUntil = [DateTime]::Now.AddSeconds(6)
                                $postTicket = $null
                            }
                        } catch {}
                    }
                }
            }

            # keep the audio going: restart if it has been silent for a while (with growing patience)
            if ($held -or (Test-CreekPlaying $p)) { $quietSince = $null; $backoff = 15 }
            elseif (-not $quietSince) { $quietSince = $t }
            elseif (-not $offline -and ($t - $quietSince).TotalSeconds -ge $backoff) {
                Start-CreekPlayer $p
                $quietSince = $null
                $backoff = [Math]::Min($backoff * 2, 120)
            }

            if (-not $quiet) {
                $frame++
                foreach ($d in $drops) { $d.Pos++ }
                foreach ($d in @($drops | Where-Object { $_.Pos -ge $riverWidth - 1 })) { $drops.Remove($d) }
                $at = @{}
                foreach ($d in $drops) { $at[[int]$d.Pos] = $d.Glyph }
                $shift = [int][Math]::Floor($frame / 2.5)
                $sb = New-Object System.Text.StringBuilder
                $i = 0
                while ($i -lt $riverWidth) {
                    if ($at.ContainsKey($i)) { [void]$sb.Append($at[$i]); $i += 2 }
                    else {
                        $j = (($i - $shift) % $water.Length + $water.Length) % $water.Length
                        [void]$sb.Append($water[$j]); $i++
                    }
                }
                if ($offline) { $text = '~ waiting for the stream ~' }
                elseif ($flash -and [DateTime]::Now -lt $flashUntil) { $text = $flash }
                elseif (-not $now) { $text = '~ joining ~' }
                elseif ($now.quiet) { $text = "quiet water - no music yet (a posts a song)  .  $($now.here) here" }
                else {
                    $song = (@($now.title, $now.artist) | Where-Object { $_ }) -join ' - '
                    $mark = $note
                    if ($now.paused) { $mark = 'paused .' }
                    $text = "$mark $song  .  "
                    if ($now.dur) { $text += "$(Format-CreekTime $now.pos)/$(Format-CreekTime $now.dur)  .  " }
                    $text += "$($now.here) here"
                    if (@($now.upnext).Count -gt 0) {
                        $text += "  .  up next: $(@($now.upnext)[0])"
                        if ($now.queued -gt 1) { $text += " +$($now.queued - 1)" }
                    }
                    elseif ($now.next) { $text += "  .  up next: $($now.next) (shuffle)" }
                }
                if ($p.Kind -ne 'ffplay') { $text += "  .  vol $($p.Volume)" }
                $w = Get-CreekWidth
                $line = "$($sb.ToString())  $text"
                if ($line.Length -gt $w - 1) { $line = $line.Substring(0, $w - 1) }
                [Console]::Write("`r" + $line.PadRight($w - 1))
            }
            Start-Sleep -Milliseconds 200
        }
    } finally {
        Stop-CreekPlayer $p
        if (-not $quiet) {
            [Console]::Write("`r" + (' ' * ((Get-CreekWidth) - 1)) + "`r")
            try { [Console]::CursorVisible = $true } catch {}
            [Console]::TreatControlCAsInput = $oldCtrlC
            [Console]::OutputEncoding = $oldEncoding
        }
    }
}

# --- adding music ----------------------------------------------------------------------------

$CreekAudioExts = @('.mp3', '.flac', '.ogg', '.oga', '.opus', '.m4a', '.aac', '.wav', '.webm', '.wma', '.mka')

function Add-CreekMusic($base, $items) {
    if (-not $items -or $items.Count -eq 0) { Write-Host 'usage: creek add <youtube link | file | folder> ...'; return }
    foreach ($item in $items) {
        if ($item -match '^https?://') { Add-CreekLink $base $item }
        elseif (Test-Path -LiteralPath $item -PathType Container) {
            $files = @(Get-ChildItem -LiteralPath $item -Recurse -File | Where-Object { $CreekAudioExts -contains $_.Extension.ToLower() })
            if ($files.Count -eq 0) { Write-Host "${item}: no audio files in there" }
            foreach ($f in $files) { Send-CreekFile $base $f }
        }
        elseif (Test-Path -LiteralPath $item -PathType Leaf) { Send-CreekFile $base (Get-Item -LiteralPath $item) }
        else { Write-Host "${item}: not a link, file or folder" }
    }
}

function Add-CreekLink($base, $link) {
    try {
        $t = Invoke-RestMethod -Method Post -Uri "$base/add/link?url=$([Uri]::EscapeDataString($link))" -UseBasicParsing
        Write-Host -NoNewline "${link}: queued"
        do {
            Start-Sleep -Seconds 2
            $s = Invoke-RestMethod -Uri "$base/add/$($t.ticket)" -UseBasicParsing
            Write-Host -NoNewline '.'
        } while (@('done', 'failed') -notcontains $s.status)
        Write-Host ''
        Write-Host "${link}: $($s.msg)"
    } catch { Write-Host ''; Write-Host "${link}: $(Get-CreekError $_)" }
}

function Send-CreekFile($base, $file) {
    if ($file.Length -gt 50MB) { Write-Host "$($file.Name): too big (max 50 MB)"; return }
    try {
        $r = Invoke-RestMethod -Method Post -Uri "$base/add/file?name=$([Uri]::EscapeDataString($file.Name))" `
            -InFile $file.FullName -ContentType 'application/octet-stream' -UseBasicParsing -TimeoutSec 120
        Write-Host "$($file.Name): $($r.msg)"
    } catch { Write-Host "$($file.Name): $(Get-CreekError $_)" }
}

# --- install ---------------------------------------------------------------------------------

function Install-Creek($base) {
    $dir = Join-Path $env:USERPROFILE '.creek'
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
    $ps1 = Join-Path $dir 'creek.ps1'
    $script = Invoke-RestMethod -Uri "$base/win" -UseBasicParsing
    Set-Content -LiteralPath $ps1 -Value $script -Encoding ASCII
    $bin = Join-Path $env:LOCALAPPDATA 'Microsoft\WindowsApps'
    New-Item -ItemType Directory -Force -Path $bin | Out-Null
    $cmd = "@echo off`r`npowershell -NoLogo -NoProfile -ExecutionPolicy Bypass -File `"$ps1`" %*`r`n"
    Set-Content -LiteralPath (Join-Path $bin 'creek.cmd') -Value $cmd -Encoding ASCII
    Write-Host "installed. type 'creek' to join, 'creek add <link|file|folder>' to add music."
    Write-Host "(open a new terminal window first if 'creek' isn't found)"
}

Invoke-Creek @args

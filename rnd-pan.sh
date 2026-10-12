#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
APP="$SCRIPT_DIR/rnd-pan.py"
STATE_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/rnd-pan"
RUNTIME_DIR="${XDG_RUNTIME_DIR:-$HOME/.local/run}/rnd-pan"
PID_FILE="$RUNTIME_DIR/rnd-pan.pid"
LOG_FILE="$STATE_DIR/rnd-pan.log"
PYTHON="${PYTHON:-python3}"

mkdir -p -- "$STATE_DIR" "$RUNTIME_DIR"

is_our_process() {
    local pid="${1:-}" cmd
    [[ "$pid" =~ ^[0-9]+$ ]] || return 1
    kill -0 "$pid" 2>/dev/null || return 1
    cmd="$(ps -p "$pid" -o args= 2>/dev/null)" || return 1
    [[ "$cmd" == *"$APP"* ]]
}

read_pid() {
    [[ -f "$PID_FILE" ]] || return 1
    cat -- "$PID_FILE"
}

find_all_instances() {
    # Exact script path match in the process command line; exclude this wrapper.
    local proc_dir pid cmd self_pid="$$"
    for proc_dir in /proc/[0-9]*; do
        [[ -r "$proc_dir/cmdline" ]] || continue
        pid="${proc_dir##*/}"
        [[ "$pid" != "$self_pid" && "$pid" != "$PPID" ]] || continue
        cmd="$(tr '\0' ' ' < "$proc_dir/cmdline" 2>/dev/null || true)"
        [[ "$cmd" == *"$APP"* ]] || continue
        [[ "$cmd" == *python* ]] || continue
        printf '%s\n' "$pid"
    done
}

start_app() {
    [[ -f "$APP" ]] || { echo "HIBA: Nem találom: $APP"; exit 1; }
    command -v "$PYTHON" >/dev/null 2>&1 || {
        echo "HIBA: Nem találom a Python-interpretert: $PYTHON"; exit 1;
    }

    local pid
    if pid="$(read_pid 2>/dev/null)" && is_our_process "$pid"; then
        echo "A program már fut. PID: $pid"
        exit 0
    fi
    rm -f -- "$PID_FILE"

    mapfile -t instances < <(find_all_instances)
    if ((${#instances[@]} > 0)); then
        echo "Már fut legalább egy RND PAN-példány: ${instances[*]}"
        echo "Ha több példány fut, állítsd le őket ezzel:"
        echo "  $0 killall"
        exit 1
    fi

    echo "RND PAN indítása..."
    nohup "$PYTHON" -u "$APP" >> "$LOG_FILE" 2>&1 </dev/null &
    pid=$!
    printf '%s\n' "$pid" > "$PID_FILE"
    sleep 1

    if is_our_process "$pid"; then
        echo "A program elindult. PID: $pid"
        echo "Napló: $LOG_FILE"
    else
        rm -f -- "$PID_FILE"
        echo "HIBA: A program nem indult el, vagy azonnal leállt."
        tail -n 30 "$LOG_FILE" 2>/dev/null || true
        exit 1
    fi
}

stop_pid() {
    local pid="$1" i
    is_our_process "$pid" || return 0
    kill -TERM "$pid" 2>/dev/null || true
    for ((i=0; i<20; i++)); do
        is_our_process "$pid" || return 0
        sleep 0.5
    done
    echo "A PID $pid nem állt le 10 másodperc alatt; kényszerített leállítás."
    kill -KILL "$pid" 2>/dev/null || true
    sleep 0.2
    ! is_our_process "$pid"
}

stop_app() {
    local pid
    if ! pid="$(read_pid 2>/dev/null)"; then
        echo "Nincs PID-fájl. Ha több példány fut, használd: $0 killall"
        exit 1
    fi
    if ! is_our_process "$pid"; then
        echo "Elavult PID-fájl eltávolítása."
        rm -f -- "$PID_FILE"
        return 0
    fi
    echo "Leállítás kérése (PID: $pid)..."
    if stop_pid "$pid"; then
        rm -f -- "$PID_FILE"
        echo "A program leállt."
    else
        echo "HIBA: A folyamat nem állt le. PID: $pid"
        exit 1
    fi
}

killall_app() {
    local pid failed=0
    mapfile -t instances < <(find_all_instances)

    if ((${#instances[@]} == 0)); then
        echo "Nem található futó RND PAN-példány."
        rm -f -- "$PID_FILE"
        return 0
    fi

    echo "Leállítandó RND PAN-példányok: ${instances[*]}"
    for pid in "${instances[@]}"; do
        if stop_pid "$pid"; then
            echo "Leállítva: PID $pid"
        else
            echo "HIBA: Nem sikerült leállítani: PID $pid"
            failed=1
        fi
    done

    if [[ -f "$PID_FILE" ]]; then
        pid="$(cat -- "$PID_FILE" 2>/dev/null || true)"
        if ! is_our_process "$pid"; then
            rm -f -- "$PID_FILE"
        fi
    fi

    ((failed == 0)) || exit 1
    echo "Az összes azonosított RND PAN-példány leállt."
}

status_app() {
    local pid
    if pid="$(read_pid 2>/dev/null)" && is_our_process "$pid"; then
        echo "A program fut. PID: $pid"
        echo "Napló: $LOG_FILE"
    else
        mapfile -t instances < <(find_all_instances)
        if ((${#instances[@]} > 0)); then
            echo "Futó példány(ok), de a PID-fájl nem jelöli őket: ${instances[*]}"
            echo "Tömeges leállítás: $0 killall"
        else
            echo "A program nem fut."
        fi
        rm -f -- "$PID_FILE"
    fi
}

show_log() {
    touch "$LOG_FILE"
    tail -n 50 -f "$LOG_FILE"
}

case "${1:-start}" in
    start)   start_app ;;
    stop)    stop_app ;;
    killall) killall_app ;;
    restart) stop_app || true; start_app ;;
    status)  status_app ;;
    log)     show_log ;;
    *)
        echo "Használat: $0 {start|stop|killall|restart|status|log}"
        exit 2
        ;;
esac

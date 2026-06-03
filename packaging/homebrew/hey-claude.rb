# Homebrew formula for hey-claude.
#
# This installs the system library (PortAudio) Homebrew is good at, pins a
# compatible Python, and lets pip build the heavy ML wheels (numpy, onnxruntime,
# openwakeword, mlx-whisper) into an isolated virtualenv at install time —
# vendoring those as `resource` blocks is impractical given their size and the
# MLX/Metal build. `claude` itself is not a Homebrew dependency; the caveats
# point users at it.
#
# To ship this as a tap:
#   1. create github.com/tachyurgy/homebrew-tap
#   2. drop this file in Formula/hey-claude.rb
#   3. set `url`/`sha256` to a tagged release tarball
#   users then: brew install tachyurgy/tap/hey-claude
class HeyClaude < Formula
  include Language::Python::Virtualenv

  desc "Say 'Hey Claude' to dispatch a Claude Code background agent — on-device voice wake word"
  homepage "https://github.com/tachyurgy/hey-claude"
  url "https://github.com/tachyurgy/hey-claude/archive/refs/tags/v0.1.0.tar.gz"
  sha256 "0000000000000000000000000000000000000000000000000000000000000000" # set on release
  license "MIT"

  depends_on "portaudio"
  depends_on "python@3.12"
  depends_on :macos
  depends_on arch: :arm64

  def install
    # Build into a venv and let pip resolve the ML stack from PyPI wheels.
    venv = virtualenv_create(libexec, "python3.12")
    system libexec/"bin/pip", "install", "-v", "--no-deps", buildpath
    system libexec/"bin/pip", "install", "-v",
           "numpy", "sounddevice", "openwakeword", "onnxruntime", "mlx-whisper"
    bin.install_symlink libexec/"bin/hey-claude"
    bin.install_symlink libexec/"bin/heyclaude"
  end

  def caveats
    <<~EOS
      hey-claude needs Claude Code (>= 2.1.139) on your PATH:
        https://code.claude.com   →   then run:  claude --version

      First-run setup (a "hey claude" wake word ships in the box — no training):
        hey-claude doctor          # checks mic, claude, models
        hey-claude                 # start listening immediately
        hey-claude models          # see / switch bundled wake words
        hey-claude agent use codex # optional: drive a different agent CLI

      Microphone permission: grant it to your terminal on first run, or build a
      permission-stable app:
        hey-claude app

      Uninstalling? Run the teardown BEFORE `brew uninstall` — Homebrew can't
      reach the config dir, your trained models, or ~/Applications:
        hey-claude uninstall --all
      (then revoke mic access in System Settings -> Privacy -> Microphone).
    EOS
  end

  test do
    assert_match "hey-claude", shell_output("#{bin}/hey-claude --version")
    assert_match "models directory", shell_output("#{bin}/hey-claude models")
  end
end

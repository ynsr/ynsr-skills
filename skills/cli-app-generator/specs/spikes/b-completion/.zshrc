PS1='%# '
export PATH="/home/bs/projects/personal/ynsr-skills/.worktrees/cli-app-generator-v2/skills/cli-app-generator/specs/spikes/b-completion/bin:/home/linuxbrew/.linuxbrew/bin:/usr/local/bin:/usr/bin:/bin"
export SPIKE_ITEMS_DIR=/tmp/spikehome/.config/spike-items
fpath=(/tmp/spikehome/zfunc $fpath)
autoload -Uz compinit
compinit

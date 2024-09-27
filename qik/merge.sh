# Custom merge driver to keep "our" version in both merge and rebase scenarios
# Installed automatically when using the repo cache.

# Determine if we're in a rebase or merge
if [ -d ".git/rebase-apply" ] || [ -d ".git/rebase-merge" ]; then
    # We're in a rebase, so "theirs" is actually what we want to keep
    cp "$3" "$2"
else
    # We're in a merge, so "ours" is what we want to keep
    # This is effectively a no-op since $2 is already "ours"
    :
fi

# The script succeeded (0 = success, 1 = failed)
exit 0

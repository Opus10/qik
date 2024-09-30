# CLI Examples

### Watch Repo-Cached Commands

```bash
qik --cache repo --watch
```

### Run All Commands Serially

```bash
qik -n 1
```

### Check for Warm Cache for Specific Commands

```bash
qik command_one command_two --cache-status warm --ls
```

### Fail if Commands have Cold Cache

```bash
qik --cache-status cold --ls --fail
```

### Run Commands Since `main` Branch

```bash
qik --since main
```

### Show Output of Successful and Failed Commands

```bash
qik -v 2
```

### Cache All Finished Commands

```bash
qik --cache-when finished
```

### Set the Default Cache

```bash
qik --cache remote_cache_name
```

import qik.conf
import qik.func


@qik.func.cache
def lock_cmd_name() -> str:
    plugin_name = qik.conf.plugin_locator("qik.uv", by_pyimport=True)[0]
    return f"{plugin_name}.lock"


@qik.func.cache
def install_cmd_name() -> str:
    plugin_name = qik.conf.plugin_locator("qik.uv", by_pyimport=True)[0]
    return f"{plugin_name}.install"

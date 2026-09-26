#include <Python.h>
#include <libgen.h>
#include <limits.h>
#include <mach-o/dyld.h>
#include <stdlib.h>
#include <string.h>

static const char *DEFAULT_MODULE = "zoya.app";
static const char *AGENT_ARG = "--agent";
static const int EXIT_REFUSED = 2;

static const char *ALLOWED_MODULES[] = {
    "zoya.app",
    "zoya.overlay",
    "zoya.permissions",
    "zoya.setup_models",
};

static const char *SEARCH_PATHS[] = {
    "Resources/app",
    "Resources/python/lib/python3.12",
    "Resources/python/lib/python3.12/lib-dynload",
    "Resources/python/lib/python3.12/site-packages",
};

static int allowed_module(int argc, char **argv) {
    if (argc < 3 || strcmp(argv[1], "-m") != 0) {
        return 0;
    }
    for (size_t i = 0; i < sizeof ALLOWED_MODULES / sizeof ALLOWED_MODULES[0]; i++) {
        if (strcmp(argv[2], ALLOWED_MODULES[i]) == 0) {
            return 1;
        }
    }
    return 0;
}

static int app_launch(int argc, char **argv) {
    return argc == 1 || strcmp(argv[1], AGENT_ARG) == 0;
}

static PyStatus set_search_paths(PyConfig *config, const char *contents) {
    char path[PATH_MAX];
    config->module_search_paths_set = 1;
    for (size_t i = 0; i < sizeof SEARCH_PATHS / sizeof SEARCH_PATHS[0]; i++) {
        snprintf(path, sizeof path, "%s/%s", contents, SEARCH_PATHS[i]);
        wchar_t *wide = Py_DecodeLocale(path, NULL);
        if (wide == NULL) {
            return PyStatus_NoMemory();
        }
        PyStatus status = PyWideStringList_Append(&config->module_search_paths, wide);
        PyMem_RawFree(wide);
        if (PyStatus_Exception(status)) {
            return status;
        }
    }
    return PyStatus_Ok();
}

static int resolve_contents(char *contents) {
    char raw[PATH_MAX];
    char resolved[PATH_MAX];
    uint32_t size = sizeof raw;
    if (_NSGetExecutablePath(raw, &size) != 0 || realpath(raw, resolved) == NULL) {
        return -1;
    }
    char *macos = dirname(resolved);
    snprintf(contents, PATH_MAX, "%s/..", macos);
    return realpath(contents, resolved) == NULL ? -1 : (strlcpy(contents, resolved, PATH_MAX), 0);
}

static PyStatus configure(PyConfig *config, const char *contents, int argc, char **argv) {
    char path[PATH_MAX];
    PyStatus status;
    snprintf(path, sizeof path, "%s/Resources/python", contents);
    status = PyConfig_SetBytesString(config, &config->home, path);
    if (PyStatus_Exception(status)) {
        return status;
    }
    status = set_search_paths(config, contents);
    if (PyStatus_Exception(status)) {
        return status;
    }
    config->use_environment = 0;
    config->user_site_directory = 0;
    config->write_bytecode = 0;
    config->safe_path = 1;
    config->buffered_stdio = 0;
    if (allowed_module(argc, argv)) {
        return PyConfig_SetBytesArgv(config, argc, argv);
    }
    char **full = calloc((size_t)argc + 3, sizeof(char *));
    full[0] = argv[0];
    full[1] = "-m";
    full[2] = (char *)DEFAULT_MODULE;
    for (int i = 1; i < argc; i++) {
        full[i + 2] = argv[i];
    }
    status = PyConfig_SetBytesArgv(config, argc + 2, full);
    free(full);
    return status;
}

int main(int argc, char **argv) {
    if (!allowed_module(argc, argv) && !app_launch(argc, argv)) {
        fprintf(stderr, "Zoya only runs her own code.\n");
        return EXIT_REFUSED;
    }
    char contents[PATH_MAX];
    if (resolve_contents(contents) != 0) {
        fprintf(stderr, "Zoya could not find its own bundle.\n");
        return 1;
    }
    PyConfig config;
    PyConfig_InitPythonConfig(&config);
    PyStatus status = configure(&config, contents, argc, argv);
    if (!PyStatus_Exception(status)) {
        status = Py_InitializeFromConfig(&config);
    }
    PyConfig_Clear(&config);
    if (PyStatus_Exception(status)) {
        Py_ExitStatusException(status);
    }
    return Py_RunMain();
}

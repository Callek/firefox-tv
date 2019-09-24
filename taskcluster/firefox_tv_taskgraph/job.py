from __future__ import absolute_import, print_function, unicode_literals

from os import path

from six import text_type
from taskgraph.transforms.job import run_job_using, configure_taskdesc_for_run
from voluptuous import Required, Schema, Optional
from pipes import quote as shell_quote

gradlew_schema = Schema({
    Required("using"): "gradlew",
    Required("gradlew"): [text_type],
    Optional("post-gradlew"): [[text_type]],
    # Base work directory used to set up the task.
    Required("workdir"): text_type,
    Optional("use-caches"): bool,
    Optional("secrets"): [{
        Required("name"): text_type,
        Required("path"): text_type,
        Required("key"): text_type,
        Optional("json"): bool,
    }]
})

@run_job_using("docker-worker", "gradlew", schema=gradlew_schema)
def configure_gradlew(config, job, taskdesc):
    run = job["run"]
    worker = taskdesc["worker"] = job["worker"]

    worker.setdefault("env", {}).update(
        {"ANDROID_SDK_ROOT": path.join(run["workdir"], "android-sdk-linux")}
    )

    # defer to the run_task implementation
    run["command"] = _extract_command(run)
    secrets = run.pop("secrets", [])
    scopes = taskdesc.setdefault("scopes", [])
    scopes.extend(["secrets:get:{}".format(secret(["name"]) for secret in secrets)])

    run["cwd"] = "{checkout}"
    run["using"] = "run-task"
    configure_taskdesc_for_run(config, job, taskdesc, job["worker"]["implementation"])


def _extract_command(run):
    pre_gradle_commands = [[
        _generate_secret_command(secret) for secret in run.get("secrets", [])
    ]]

    gradle_command = ["./gradlew"] + run.pop("gradlew")
    post_gradle_commands = run.pop("post-gradlew", [])

    commands = pre_gradle_commands + [gradle_command] + post_gradle_commands
    shell_quoted_commands = [" ".join(map(shell_quote, command)) for command in commands]
    return " && ".join(shell_quoted_commands)


def _generate_secret_command(secret):
    secret_command = [
        "taskcluster/scripts/get-secret.py",
        "-s", secret["name"],
        "-k", secret["key"],
        "-f", secret["path"],
    ]
    if secret.get("json"):
        secret_command.append("--json")

    return secret_command
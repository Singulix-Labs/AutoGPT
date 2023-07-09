import json
import os
import shutil
from pathlib import Path  # noqa
from typing import Any, Dict, Generator

import pytest

from agbenchmark.RegressionManager import RegressionManager
from agbenchmark.start_benchmark import (
    CONFIG_PATH,
    REGRESSION_TESTS_PATH,
    get_regression_data,
)


def resolve_workspace(config: Dict[str, Any]) -> str:
    if config.get("workspace", "").startswith("${") and config.get(
        "workspace", ""
    ).endswith("}"):
        # Extract the string inside ${...}
        path_expr = config["workspace"][2:-1]

        # Check if it starts with "os.path.join"
        if path_expr.strip().startswith("os.path.join"):
            # Evaluate the path string
            path_value = eval(path_expr)

            # Replace the original string with the evaluated result
            return path_value
        else:
            raise ValueError("Invalid workspace path expression.")
    else:
        return os.path.abspath(Path(os.getcwd()) / config["workspace"])


@pytest.fixture(scope="module")
def config(request: Any) -> None:
    print(f"Config file: {CONFIG_PATH}")
    with open(CONFIG_PATH, "r") as f:
        config = json.load(f)

    if request.config.getoption("--mock"):
        config["workspace"] = "agbenchmark/workspace"
    elif isinstance(config["workspace"], str):
        config["workspace"] = resolve_workspace(config)
    else:  # it's a input output dict
        config["workspace"]["input"] = resolve_workspace(config)
        config["workspace"]["output"] = resolve_workspace(config)

    return config


@pytest.fixture(scope="module", autouse=True)
def workspace(config: Dict[str, Any]) -> Generator[str, None, None]:
    output_path = config["workspace"]

    # checks if its an input output paradigm
    if not isinstance(config["workspace"], str):
        output_path = config["workspace"]["output"]
        if not os.path.exists(config["workspace"]["input"]):
            os.makedirs(config["workspace"]["input"], exist_ok=True)

    # create output directory if it doesn't exist
    if not os.path.exists(output_path):
        os.makedirs(output_path, exist_ok=True)

    yield config["workspace"]
    # teardown after test function completes

    for filename in os.listdir(output_path):
        file_path = os.path.join(output_path, filename)
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
        except Exception as e:
            print(f"Failed to delete {file_path}. Reason: {e}")


def pytest_addoption(parser: Any) -> None:
    parser.addoption("--mock", action="store_true", default=False)
    parser.addoption("--improve", action="store_true", default=False)
    parser.addoption("--maintain", action="store_true", default=False)


@pytest.fixture(autouse=True)
def check_regression(request: Any) -> None:
    test_name = request.node.parent.name
    data = get_regression_data()

    # Check if the test name exists in the regression tests
    if request.config.getoption("--improve") and data.get(test_name, None):
        pytest.skip("Skipping test because it's a regression test and --improve is set")
    elif request.config.getoption("--maintain") and not data.get(test_name, None):
        pytest.skip(
            "Skipping test because it's not a regression test and --maintain is set"
        )


# this is to get the challenge_data from every test
@pytest.fixture(autouse=True)
def challenge_data(request: Any) -> None:
    return request.param


regression_manager = RegressionManager(REGRESSION_TESTS_PATH)


def pytest_runtest_makereport(item: Any, call: Any) -> None:
    if call.when == "call":
        challenge_data = item.funcargs.get("challenge_data", None)
        difficulty = challenge_data.info.difficulty if challenge_data else "unknown"
        dependencies = challenge_data.dependencies if challenge_data else []
        parts = item.nodeid.split("::")[0].split("/")
        agbenchmark_index = parts.index("agbenchmark")
        file_path = "/".join(parts[agbenchmark_index:])
        test_details = {
            "difficulty": difficulty,
            "dependencies": dependencies,
            "test": file_path,
        }

        print("pytest_runtest_makereport", test_details)
        if call.excinfo is None:
            regression_manager.add_test(item.nodeid.split("::")[1], test_details)
        else:
            regression_manager.remove_test(item.nodeid.split("::")[1])


def pytest_sessionfinish() -> None:
    """Called at the end of the session to save regression tests"""
    regression_manager.save()


# this is so that all tests can inherit from the Challenge class
def pytest_generate_tests(metafunc: Any) -> None:
    if "challenge_data" in metafunc.fixturenames:
        # Get the instance of the test class
        test_class = metafunc.cls()

        # Generate the parameters
        params = test_class.data

        # Add the parameters to the test function
        metafunc.parametrize("challenge_data", [params], indirect=True)


# this is adding the dependency marker and category markers automatically from the json
def pytest_collection_modifyitems(items: Any, config: Any) -> None:
    data = get_regression_data()

    for item in items:
        # Assuming item.cls is your test class
        test_class_instance = item.cls()

        # Then you can access your properties
        name = item.parent.cls.__name__
        dependencies = test_class_instance.data.dependencies

        # Filter dependencies if they exist in regression data if its an improvement test
        if config.getoption("--improve"):
            dependencies = [dep for dep in dependencies if not data.get(dep, None)]

        categories = test_class_instance.data.category

        # Add depends marker dynamically
        item.add_marker(pytest.mark.depends(on=dependencies, name=name))

        # Add category marker dynamically
        for category in categories:
            item.add_marker(getattr(pytest.mark, category))

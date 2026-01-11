# Developer documentation

## Setup development environment

To setup your development environment for this custom integration, follow these steps:

> This is tested under windows using VS Code. As the repo is container based, it should work in other environments as well.

- Clone this repository
- Open the repo in devcontainer
- When the devcontainer is setup
  - Run HA with `scripts/develop` manually
  - Generate a Home Assistant Authentication Token (this is needed to run the integration tests, see BELOW)
    - Connect to the running Home Assistant instance via http://localhost:8123
    - Generate tokens in Home Assistant: Settings > Devices & Services > Your Name > Create Token
- On the host (not in the container), set the environment variable HA_TOKEN_DEV and rebuild the container
  - In this way, you will be able to run the integration test from any shell in the container
  - Alternatively, you can set the token in the needed shell inside the container
    - e.g. via a `.env-file` (see `.env.example`)

## Run Tests

Before running the integration tests the first time, run HA with `scripts/develop` manually and wait until its fnished (you can connect via via http://localhost:8123). Then stop HA - the integration tests setup a new DB and start the HA on its own, when the HA is running already, the tests will not work.

Start all tests with `pytest`.

See [Testing Strategy](./architecture.md#testing-strategy) for more information regarding tests.

## Architecture / design description

Architecture / design description see [architecture.md](./architecture.md).

## Contributing

Contributions are welcome! Please read the [Contribution Guidelines](CONTRIBUTING.md).

# WebOps CLI

Command-line interface for the WebOps hosting platform.

## Installation

```bash
pip install webops-cli
```

Or install from source:

```bash
cd cli
pip install -e .
```

## Configuration

```bash
webops config --url https://panel.yourdomain.com --token YOUR_API_TOKEN
```

## Usage

### Deploy an application
```bash
webops deploy --repo https://github.com/user/repo --name myapp --domain myapp.com
```

### List deployments
```bash
webops list
```

### View deployment details
```bash
webops info myapp
```

### View logs
```bash
webops logs myapp --tail 100 --follow
```

### Control services
```bash
webops start myapp
webops stop myapp
webops restart myapp
```

### Delete deployment
```bash
webops delete myapp
```

## API Token

Generate an API token from the WebOps control panel:

1. Login to WebOps
2. Navigate to Settings → API Tokens
3. Create a new token
4. Copy the token and use it with `webops config`

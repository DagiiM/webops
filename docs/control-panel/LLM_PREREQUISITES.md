# LLM Deployment Prerequisites

This document describes the system prerequisites required for deploying LLM models with vLLM and how to configure automatic installation.

## Required Packages

WebOps requires the following system packages to build and run vLLM-based LLM deployments:

### Build Tools
- **build-essential**: GNU C/C++ compiler (gcc, g++) and build tools (make)
- **cmake**: CMake build system for configuring builds
- **ninja-build**: Ninja build tool (faster alternative to make)

### Development Headers
- **python3-dev**: Python development headers (required for building Python extensions)
- **libnuma-dev**: NUMA (Non-Uniform Memory Access) development library (required for vLLM CPU builds)

### Runtime Libraries
- **libgomp1**: GNU OpenMP runtime library (required for parallel processing)

## Automatic Installation

WebOps can automatically install missing prerequisites if passwordless sudo is configured.

### Configure Passwordless Sudo

1. **Edit the sudoers file**:
   ```bash
   sudo visudo
   ```

2. **Add the following line** (replace `username` with your actual username or use `%groupname` for a group):
   ```
   username ALL=(ALL) NOPASSWD: /usr/bin/apt-get update, /usr/bin/apt-get install
   ```

   Or for a group (e.g., `webops` group):
   ```
   %webops ALL=(ALL) NOPASSWD: /usr/bin/apt-get update, /usr/bin/apt-get install
   ```

3. **Save and exit** (Ctrl+X, then Y, then Enter)

4. **Test the configuration**:
   ```bash
   sudo -n apt-get update
   ```
   This should run without asking for a password.

### Security Considerations

The sudo configuration above only grants permission to run `apt-get update` and `apt-get install`. This is relatively safe because:

- It doesn't grant full root access
- It only allows package installation from configured repositories
- It doesn't allow running arbitrary commands

However, you should still:
- Only configure this on dedicated deployment servers
- Ensure your APT sources are trustworthy
- Monitor package installations via logs

## Manual Installation

If you prefer not to configure automatic installation, you can install all prerequisites manually:

```bash
sudo apt-get update && sudo apt-get install -y \
  build-essential \
  cmake \
  ninja-build \
  python3-dev \
  libnuma-dev \
  libgomp1
```

## How It Works

When you create an LLM deployment, WebOps:

1. **Checks for prerequisites**: Scans the system for required packages
2. **Attempts automatic installation**: If sudo is available and packages are missing, installs them automatically
3. **Provides manual instructions**: If sudo is not available, provides detailed installation instructions
4. **Proceeds with deployment**: Once all prerequisites are present, continues with vLLM setup

## Troubleshooting

### "Missing required build dependencies" Error

If you see this error, WebOps detected missing packages but couldn't install them automatically.

**Solutions**:
1. Configure passwordless sudo (see above)
2. Install packages manually using the provided command
3. Check the deployment logs for specific missing packages

### "Sudo access not available" Warning

This means WebOps couldn't verify passwordless sudo access.

**Solutions**:
1. Verify your sudoers configuration
2. Test with: `sudo -n true`
3. Check that your user has sudo privileges

### Build Still Fails After Installing Prerequisites

If the build fails with errors like "numa.h: No such file or directory" even after installation:

1. **Verify package installation**:
   ```bash
   dpkg -l | grep libnuma-dev
   ```

2. **Check header file exists**:
   ```bash
   ls /usr/include/numa.h
   ```

3. **Reinstall the package**:
   ```bash
   sudo apt-get install --reinstall libnuma-dev
   ```

4. **Clear any cached build files** and retry the deployment

### Permission Errors During Installation

If you see permission errors:

1. Check your user has sudo privileges: `sudo -l`
2. Verify the sudoers file is correctly formatted
3. Try manual installation to confirm the packages are available

## Package Verification

You can manually verify all prerequisites are installed:

```bash
# Check build tools
which gcc g++ cmake ninja

# Check Python headers
python3 -c "import sysconfig; print(sysconfig.get_path('include'))"

# Check NUMA headers
ls /usr/include/numa.h

# Check OpenMP library
ls /usr/lib/x86_64-linux-gnu/libgomp.so.1
```

All commands should succeed without errors.

## Alternative: Docker-based Deployments

If you prefer not to install system packages on your host, consider using Docker-based LLM deployments (if the Docker addon is enabled). Docker containers include all necessary build dependencies.

## Environment-Specific Notes

### Ubuntu/Debian
The instructions above are for Ubuntu/Debian-based systems using APT package manager.

### WSL (Windows Subsystem for Linux)
WSL environments should work the same as native Ubuntu. Ensure your WSL distribution has network access to download packages.

### Other Linux Distributions
For other distributions:
- **Fedora/RHEL/CentOS**: Use `dnf` instead of `apt-get`
- **Arch Linux**: Use `pacman` instead of `apt-get`
- **Alpine Linux**: Use `apk` instead of `apt-get`

Package names may differ slightly between distributions.

## Monitoring Prerequisite Installation

Prerequisite installation is logged in:
1. **Django logs**: Check your Django application logs
2. **Deployment logs**: View in the WebOps UI under deployment details
3. **System logs**: Check `/var/log/syslog` for apt-get activity

## Production Recommendations

For production environments:

1. **Pre-install all prerequisites** during server provisioning
2. **Use configuration management** (Ansible, Chef, Puppet) to ensure consistent setup
3. **Create a base system image** with all prerequisites installed
4. **Monitor for missing packages** in your deployment pipeline
5. **Document your setup** for disaster recovery

## Support

If you encounter issues with prerequisites:

1. Check the deployment logs for detailed error messages
2. Verify all packages are installed correctly
3. Review this documentation for troubleshooting steps
4. Check WebOps GitHub issues for similar problems
5. Create a new issue with detailed logs if needed

## References

- [vLLM Documentation](https://docs.vllm.ai/)
- [NUMA on Linux](https://www.kernel.org/doc/html/latest/vm/numa.html)
- [Ubuntu Package Management](https://help.ubuntu.com/community/AptGet/Howto)
- [Sudo Configuration](https://www.sudo.ws/docs/man/sudoers.man/)

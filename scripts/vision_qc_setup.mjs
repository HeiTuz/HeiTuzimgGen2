#!/usr/bin/env node

function platform() {
  return process.env.HEITUZ_TEST_PLATFORM || process.platform;
}

function configuredEnvironment() {
  for (const name of ["GOOGLE_API_KEY", "GEMINI_API_KEY"]) {
    if (process.env[name]?.trim()) return name;
  }
  return null;
}

function usage(code = 0) {
  const out = code === 0 ? console.log : console.error;
  out(`HeiTuz Vision-QC setup

Usage:
  heituz vision-qc setup
  heituz vision-qc status

Vision QC uses a Google AI Studio API key only for post-generation thumbnail review.
The key stays in the current terminal session and is never written by this tool.`);
  process.exit(code);
}

function printPosixSetup() {
  console.log(`Vision-QC setup (macOS/Linux)

1. Create a Google AI Studio API key:
   https://aistudio.google.com/apikey
2. In the terminal that will run QC, enter the key without echoing it:

   printf 'Google AI API key: '
   stty -echo
   IFS= read -r GOOGLE_API_KEY
   stty echo
   printf '\\n'
   export GOOGLE_API_KEY

3. Run the normal dry-run and use its request SHA-256 immediately before --execute.

The key is available only to this terminal session. Do not put it in a command line, URL, report, or repository file.`);
}

function printWindowsSetup() {
  console.log(`Vision-QC setup (Windows PowerShell)

1. Create a Google AI Studio API key:
   https://aistudio.google.com/apikey
2. In the PowerShell session that will run QC, enter the key without echoing it:

   $secure = Read-Host 'Google AI API key' -AsSecureString
   $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
   try { $env:GOOGLE_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer) }
   finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer) }

3. Run the normal dry-run and use its request SHA-256 immediately before --execute.

The key is available only to this PowerShell session. Do not put it in a command line, URL, report, or repository file.`);
}

function main(argv) {
  if (argv.length > 1 || (argv[0] && argv[0] !== "--status" && argv[0] !== "--help" && argv[0] !== "-h")) usage(2);
  if (argv[0] === "--help" || argv[0] === "-h") usage(0);
  const configured = configuredEnvironment();
  if (argv[0] === "--status") {
    console.log(JSON.stringify({ vision_qc: configured ? "configured" : "needs_api_key", api_key_environment: configured }, null, 2));
    return;
  }
  if (configured) console.log(`Vision-QC is configured for this session through ${configured}. No key value was displayed.\n`);
  if (platform() === "win32") printWindowsSetup();
  else printPosixSetup();
}

main(process.argv.slice(2));

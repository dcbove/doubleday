# iOS Release Guide

## Prerequisites

- **Apple Developer account** enrolled in the [Apple Developer Program](https://developer.apple.com/programs/)
- **Xcode** installed (latest stable recommended)
- **EAS CLI** installed globally: `npm install -g eas-cli`
- **Expo account** authenticated: `eas login`
- **Apple credentials** configured in EAS (you will be prompted on first build, or run `eas credentials`)
- Frontend dependencies installed: `make frontend-install`

## Version Bumping

Before building a release, bump the version in `frontend/app.json`:

```jsonc
{
  "expo": {
    "version": "1.1.0",       // user-facing version (App Store)
    "ios": {
      "buildNumber": "2"      // increment each submission to App Store Connect
    }
  }
}
```

- **`version`** — semver shown to users in the App Store. Bump for each new release.
- **`buildNumber`** — must be unique per submission to App Store Connect. Increment even for re-submissions of the same version.

## Local Development (Simulator)

Run the app on the iOS simulator:

```sh
make frontend-ios
```

This runs `npx expo run:ios`, which performs a native build targeting the simulator.

## On-Device Testing (Tethered iPhone)

Build a release version and install it directly on a connected iPhone:

```sh
cd frontend
npx expo run:ios --configuration Release --device
```

This performs a **local Xcode build** — it compiles entirely on your machine using your local Xcode signing configuration and installs directly over USB. It does not use EAS or `eas.json` at all.

> **Note:** Your device must be registered in your Apple Developer account and a valid provisioning profile must be configured in Xcode.

## EAS Build (Cloud Builds)

The sections below use **EAS Build**, which compiles in Expo's cloud infrastructure instead of on your machine. EAS Build is needed for TestFlight distribution and App Store submission because it handles production code signing (distribution certificates, provisioning profiles) and generates `.ipa` files suitable for App Store Connect. Build profiles are defined in `frontend/eas.json`:

| Profile         | Distribution | Use Case                                      |
|-----------------|--------------|-----------------------------------------------|
| `development`   | internal     | Dev client build for local development         |
| `preview`       | internal     | Internal testing via TestFlight or ad-hoc       |
| `production`    | store        | App Store submission                            |

## Building for TestFlight (Preview)

Build an internal preview that can be distributed to testers via TestFlight:

```sh
cd frontend
eas build --platform ios --profile preview
```

EAS will handle code signing automatically. Once the build completes, submit it to TestFlight:

```sh
eas submit --platform ios --latest
```

Or combine both steps:

```sh
eas build --platform ios --profile preview --auto-submit
```

## Building for App Store (Production)

1. **Ensure the version and build number are updated** in `frontend/app.json`.

2. **Create the production build:**

   ```sh
   cd frontend
   eas build --platform ios --profile production
   ```

3. **Submit to App Store Connect:**

   ```sh
   eas submit --platform ios --latest
   ```

   Or build and submit in one step:

   ```sh
   eas build --platform ios --profile production --auto-submit
   ```

4. **Complete the release in App Store Connect:**
   - Go to [App Store Connect](https://appstoreconnect.apple.com)
   - Select the Doubleday app (`com.appleforge.doubleday`)
   - Add the new build to a release
   - Fill in release notes, screenshots, and metadata
   - Submit for App Review

## Environment Variables

Production iOS builds use environment variables baked in at build time via the `EXPO_PUBLIC_*` prefix. For production releases, configure these in `eas.json` or via EAS Secrets.

First, extract the values from Terraform outputs:

```sh
cd terraform/environments/prod
POOL_ID=$(terraform output -raw cognito_user_pool_id)
CLIENT_ID=$(terraform output -raw cognito_client_id)
API_KEY=$(terraform output -raw api_key)
```

Then create the EAS Secrets:

```sh
eas secret:create --name EXPO_PUBLIC_COGNITO_USER_POOL_ID --value "$POOL_ID"
eas secret:create --name EXPO_PUBLIC_COGNITO_CLIENT_ID --value "$CLIENT_ID"
eas secret:create --name EXPO_PUBLIC_COGNITO_DOMAIN --value "doubleday-prod"
eas secret:create --name EXPO_PUBLIC_COGNITO_REGION --value "us-east-1"
eas secret:create --name EXPO_PUBLIC_API_URL --value "https://doubleday-prod.appleforge.com/api"
eas secret:create --name EXPO_PUBLIC_CDN_ORIGIN --value "https://doubleday-prod.appleforge.com"
eas secret:create --name EXPO_PUBLIC_API_KEY --value "$API_KEY"
eas secret:create --name EXPO_PUBLIC_REDIRECT_SIGN_IN --value "doubleday://callback"
eas secret:create --name EXPO_PUBLIC_REDIRECT_SIGN_OUT --value "doubleday://"
```

Alternatively, add an `env` block to the production profile in `frontend/eas.json`.

## Makefile Reference

| Command               | Description                                  |
|-----------------------|----------------------------------------------|
| `make frontend-install` | Install frontend npm dependencies           |
| `make frontend-ios`     | Build and run on iOS simulator              |
| `make frontend-build`   | Build frontend for web production           |
| `make frontend-deploy`  | Build and deploy web frontend (ENV=dev\|prod) |
| `make frontend-dev`     | Start web dev server (port 8081)            |
| `make frontend-clean`   | Remove node_modules and dist                |

## Checklist

- [ ] Version and build number bumped in `frontend/app.json`
- [ ] Production environment variables configured (EAS Secrets or `eas.json`)
- [ ] `make frontend-install` run successfully
- [ ] `eas build --platform ios --profile production` completed
- [ ] `eas submit --platform ios --latest` submitted to App Store Connect
- [ ] Release notes and metadata filled in App Store Connect
- [ ] App Review submitted

import { Platform } from "react-native";
import { Amplify } from "aws-amplify";

const region = process.env.EXPO_PUBLIC_COGNITO_REGION;
const domain = process.env.EXPO_PUBLIC_COGNITO_DOMAIN;

function getRedirectSignIn() {
  if (Platform.OS === "web") {
    return process.env.EXPO_PUBLIC_REDIRECT_SIGN_IN;
  }
  return "doubleday://callback";
}

function getRedirectSignOut() {
  if (Platform.OS === "web") {
    return process.env.EXPO_PUBLIC_REDIRECT_SIGN_OUT;
  }
  return "doubleday://";
}

Amplify.configure({
  Auth: {
    Cognito: {
      userPoolId: process.env.EXPO_PUBLIC_COGNITO_USER_POOL_ID,
      userPoolClientId: process.env.EXPO_PUBLIC_COGNITO_CLIENT_ID,
      loginWith: {
        oauth: {
          domain: `${domain}.auth.${region}.amazoncognito.com`,
          scopes: ["openid", "email", "profile"],
          redirectSignIn: [getRedirectSignIn()],
          redirectSignOut: [getRedirectSignOut()],
          responseType: "code",
        },
      },
    },
  },
});

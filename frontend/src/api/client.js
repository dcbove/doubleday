import { Platform } from "react-native";
import { fetchAuthSession } from "aws-amplify/auth";

async function getAccessToken() {
  const session = await fetchAuthSession();
  return session.tokens?.accessToken?.toString();
}

function getBaseUrl() {
  if (Platform.OS === "web") {
    // In production, /api is same-origin (CloudFront proxies to API GW).
    // In local dev, use the full CloudFront URL so the request still goes
    // through CloudFront (which injects x-api-key). CORS allows this since
    // API GW returns Access-Control-Allow-Origin: *.
    return process.env.EXPO_PUBLIC_API_URL || "/api";
  }
  // Mobile hits the API directly.
  return process.env.EXPO_PUBLIC_API_URL;
}

export async function apiFetch(path, options = {}) {
  const token = await getAccessToken();
  const baseUrl = getBaseUrl();

  const headers = {
    Authorization: `Bearer ${token}`,
    Accept: "application/json",
    ...options.headers,
  };

  // Only mobile sends x-api-key directly. On web, CloudFront injects it
  // server-side so the browser never sends it (avoids CORS issues).
  const apiKey = process.env.EXPO_PUBLIC_API_KEY;
  if (apiKey && Platform.OS !== "web") {
    headers["x-api-key"] = apiKey;
  }

  const response = await fetch(`${baseUrl}${path}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`;
    try {
      const body = await response.json();
      if (body.error) message = body.error;
    } catch {}
    const err = new Error(message);
    err.status = response.status;
    throw err;
  }

  return response.json();
}

export async function apiPost(path, body = {}, options = {}) {
  return apiFetch(path, {
    ...options,
    method: "POST",
    headers: { "Content-Type": "application/json", ...options.headers },
    body: JSON.stringify(body),
  });
}

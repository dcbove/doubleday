import { createContext, useState, useEffect, useCallback } from "react";
import { getCurrentUser, signInWithRedirect, signOut, fetchAuthSession } from "aws-amplify/auth";
import { Hub } from "aws-amplify/utils";

export const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  async function resolveUser() {
    try {
      const cognitoUser = await getCurrentUser();
      const session = await fetchAuthSession();
      const claims = session.tokens?.idToken?.payload;
      setUser({
        ...cognitoUser,
        name: claims?.name || claims?.email || cognitoUser.username,
        picture: claims?.picture,
      });
    } catch {
      setUser(null);
    }
  }

  useEffect(() => {
    resolveUser().finally(() => setLoading(false));

    const unsubscribe = Hub.listen("auth", ({ payload }) => {
      if (payload.event === "signInWithRedirect") {
        resolveUser();
      }
    });
    return unsubscribe;
  }, []);

  const login = useCallback(async () => {
    try {
      await getCurrentUser();
      await resolveUser();
    } catch {
      signInWithRedirect({ provider: "Google" });
    }
  }, []);

  const logout = useCallback(async () => {
    await signOut({ global: true });
    setUser(null);
  }, []);

  const getAccessToken = useCallback(async () => {
    const session = await fetchAuthSession();
    return session.tokens?.accessToken?.toString();
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, login, logout, getAccessToken }}>
      {children}
    </AuthContext.Provider>
  );
}

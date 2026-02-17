import { createContext, useState, useEffect, useCallback } from "react";
import { getCurrentUser, signInWithRedirect, signOut, fetchAuthSession } from "aws-amplify/auth";

export const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getCurrentUser()
      .then(async (cognitoUser) => {
        const session = await fetchAuthSession();
        const claims = session.tokens?.idToken?.payload;
        setUser({
          ...cognitoUser,
          name: claims?.name || claims?.email || cognitoUser.username,
          picture: claims?.picture,
        });
      })
      .catch(() => setUser(null))
      .finally(() => setLoading(false));
  }, []);

  const login = useCallback(() => {
    signInWithRedirect({ provider: "Google" });
  }, []);

  const logout = useCallback(async () => {
    await signOut();
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

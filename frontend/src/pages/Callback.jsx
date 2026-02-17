import { useEffect } from "react";
import { useNavigate } from "react-router";
import { Hub } from "aws-amplify/utils";
import { getCurrentUser } from "aws-amplify/auth";

export default function Callback() {
  const navigate = useNavigate();

  useEffect(() => {
    const unsubscribe = Hub.listen("auth", ({ payload }) => {
      if (payload.event === "signInWithRedirect") {
        navigate("/dashboard", { replace: true });
      }
    });

    // If the user is already signed in (e.g. page refresh), redirect immediately
    getCurrentUser()
      .then(() => navigate("/dashboard", { replace: true }))
      .catch(() => {});

    return unsubscribe;
  }, [navigate]);

  return (
    <div className="flex h-screen items-center justify-center">
      <p className="text-gray-500">Signing in...</p>
    </div>
  );
}

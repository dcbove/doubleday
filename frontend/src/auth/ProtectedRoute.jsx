import { Navigate, Outlet } from "react-router";
import useAuth from "./useAuth";

export default function ProtectedRoute() {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <p className="text-gray-500">Loading...</p>
      </div>
    );
  }

  return user ? <Outlet /> : <Navigate to="/" replace />;
}

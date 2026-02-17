import { Link } from "react-router";
import useAuth from "../auth/useAuth";

export default function Navbar() {
  const { user, logout } = useAuth();

  return (
    <nav className="border-b border-gray-200 bg-white">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3 sm:px-6 lg:px-8">
        <div className="flex items-center gap-6">
          <Link to="/dashboard" className="text-lg font-bold text-gray-900">
            Doubleday
          </Link>
          <Link to="/dashboard" className="text-sm text-gray-600 hover:text-gray-900">
            Dashboard
          </Link>
        </div>
        <div className="flex items-center gap-4">
          {user && (
            <div className="flex items-center gap-2">
              {user.picture && (
                <img
                  src={user.picture}
                  alt=""
                  className="h-7 w-7 rounded-full"
                  referrerPolicy="no-referrer"
                />
              )}
              <span className="hidden text-sm text-gray-600 sm:inline">
                {user.name}
              </span>
            </div>
          )}
          <button
            onClick={logout}
            className="rounded-md bg-gray-100 px-3 py-1.5 text-sm text-gray-700 hover:bg-gray-200"
          >
            Sign out
          </button>
        </div>
      </div>
    </nav>
  );
}

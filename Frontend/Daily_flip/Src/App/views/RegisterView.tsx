import { useContext, useState} from "react";
import { Eye, EyeOff, Lock, Mail, Calendar, User } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { AuthContext } from "../../Context/AuthContext";
import { Countries } from "../../Data/Countries";
import { RegisterData } from "../../Api/auth";

export default function Register() {
  const auth = useContext(AuthContext);
  const navigate = useNavigate();

  const [showPassword, setShowPassword] = useState(false);
  const [email, setEmail] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [country, setCountry] = useState("");
  const [dob, setDob] = useState("");

  const passwordsMatch = password === confirmPassword && password.length > 0;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const registerData: RegisterData = { email, password, country, dob, username };
    await auth?.register(registerData);

    console.log("Auth state after login:", auth);
    console.log("Auth token after login:", auth?.token);

    if (auth?.token) {
      navigate("/app");
    }
  };

  return (
    <div
      className="size-full flex items-center justify-center"
      style={{ backgroundColor: "#FBF8EB" }}
    >
      <div className="bg-white rounded-2xl shadow-lg w-full max-w-sm p-8 flex flex-col gap-6">
        {/* Header */}
        <div className="flex flex-col items-center gap-1">
          <div className="w-10 h-10 rounded-full bg-gray-100 flex items-center justify-center mb-1">
            <Lock size={20} className="text-gray-600" />
          </div>
          <h1 className="text-xl font-semibold text-gray-900">Welcome back</h1>
          <p className="text-sm text-gray-500">Sign in to your account</p>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          {/* Email */}
          <div className="flex flex-col gap-1.5">
            <label htmlFor="email" className="text-sm font-medium text-gray-700">
              Email
            </label>
            <div className="relative">
              <Mail
                size={16}
                className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none"
              />
              <input
                id="email"
                type="email"
                autoComplete="email"
                placeholder="you@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full pl-9 pr-3 py-2.5 text-sm border border-gray-200 rounded-lg outline-none focus:ring-2 focus:ring-gray-900 focus:border-transparent transition placeholder:text-gray-400 text-gray-900"
              />
            </div>
          </div>

          {/* Username */}
          <div className="flex flex-col gap-1.5">
            <label htmlFor="username" className="text-sm font-medium text-gray-700">
              Username
            </label>

            <div className="relative">
              <User
                size={16}
                className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none"
              />

              <input
                id="username"
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="yourusername"
                className={`w-full pl-9 pr-3 py-2.5 text-sm border rounded-lg outline-none transition
                  ${username.length === 0
                    ? "border-gray-200"
                    : username.length >= 5
                      ? "border-green-500 focus:ring-2 focus:ring-green-600"
                      : "border-red-500 focus:ring-2 focus:ring-red-600"
                  } text-gray-900`}
              />
            </div>

            {username.length > 0 && username.length < 5 && (
              <p className="text-xs text-red-500">Username must be at least 5 characters</p>
            )}
          </div>

          {/* Password */}
          <div className="flex flex-col gap-1.5">
            <div className="flex items-center justify-between">
              <label htmlFor="password" className="text-sm font-medium text-gray-700">
                Password
              </label>
              <a
                href="#"
                className="text-xs text-gray-500 hover:text-gray-900 transition"
              >
                Forgot password?
              </a>
            </div>
            <div className="relative">
              <Lock
                size={16}
                className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none"
              />
              <input
                id="password"
                type={showPassword ? "text" : "password"}
                autoComplete="current-password"
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full pl-9 pr-10 py-2.5 text-sm border border-gray-200 rounded-lg outline-none focus:ring-2 focus:ring-gray-900 focus:border-transparent transition placeholder:text-gray-400 text-gray-900"
              />
              <button
                type="button"
                onClick={() => setShowPassword((v) => !v)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 transition"
                tabIndex={-1}
              >
                {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
          </div>

          {/* Confirm Password */}
          <div className="flex flex-col gap-1.5">
            <label htmlFor="confirmPassword" className="text-sm font-medium text-gray-700">
              Confirm Password
            </label>

            <div className="relative">
              <Lock
                size={16}
                className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none"
              />

              <input
                id="confirmPassword"
                type={showPassword ? "text" : "password"}
                placeholder="••••••••"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                className={`w-full pl-9 pr-10 py-2.5 text-sm border rounded-lg outline-none transition
                  ${confirmPassword.length === 0
                    ? "border-gray-200"
                    : passwordsMatch
                      ? "border-green-500 focus:ring-green-600"
                      : "border-red-500 focus:ring-red-600"
                  }`}
              />
            </div>

            {/* Validation message */}
            {confirmPassword.length > 0 && !passwordsMatch && (
              <p className="text-xs text-red-500">Passwords do not match</p>
            )}
          </div>

          {/* Country */}
          <div className="flex flex-col gap-1.5">
            <label htmlFor="country" className="text-sm font-medium text-gray-700">
              Country
            </label>

            <div className="relative">
              <select
                id="country"
                value={country}
                onChange={(e) => setCountry(e.target.value)}
                className="w-full pl-3 pr-10 py-2.5 text-sm border border-gray-200 rounded-lg outline-none focus:ring-2 focus:ring-gray-900 focus:border-transparent transition text-gray-900 bg-white appearance-none"
              >
                <option value="">Select your country</option>

                {Countries.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>

              {/* Dropdown arrow */}
              <svg
                className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400 pointer-events-none"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                viewBox="0 0 24 24"
              >
                <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
              </svg>
            </div>
          </div>

          {/* Date of Birth */}
          <div className="flex flex-col gap-1.5">
            <label htmlFor="dob" className="text-sm font-medium text-gray-700">
              Date of Birth
            </label>

            <div className="relative">
              <Calendar
                size={16}
                className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none"
              />

              <input
                id="dob"
                type="date"
                value={dob}
                onChange={(e) => setDob(e.target.value)}
                className="w-full pl-9 pr-3 py-2.5 text-sm border border-gray-200 rounded-lg outline-none focus:ring-2 focus:ring-gray-900 focus:border-transparent transition text-gray-900 bg-white"
              />
            </div>
          </div>

          {/* Submit */}
          <button
            type="submit"
            className="mt-1 w-full py-2.5 rounded-lg bg-gray-900 text-white text-sm font-medium hover:bg-gray-700 active:bg-gray-800 transition"
          >
            Register
          </button>
        </form>

        {/* Divider */}
        <div className="flex items-center gap-3">
          <div className="flex-1 h-px bg-gray-100" />
          <span className="text-xs text-gray-400">or</span>
          <div className="flex-1 h-px bg-gray-100" />
        </div>

        {/* Sign up */}
        <p className="text-center text-sm text-gray-500">
          Don't have an account?{" "}
          <a href="#" className="text-gray-900 font-medium hover:underline">
            Sign up
          </a>
        </p>
      </div>
    </div>
  );
}
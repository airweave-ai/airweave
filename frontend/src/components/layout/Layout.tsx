import { Outlet } from "react-router-dom";

export const Layout = () => {
  return (
    <main className="min-h-screen">
      <Outlet />
    </main>
  );
};

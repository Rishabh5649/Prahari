import React from 'react';
import { BrowserRouter as Router, Routes, Route, Link } from 'react-router-dom';
import Dashboard from '@/pages/Dashboard';
import IngestPage from '@/pages/IngestPage';
import CircularDetail from '@/pages/CircularDetail';
import DepartmentView from '@/pages/DepartmentView';
import AuditPage from '@/pages/AuditPage';

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Button } from '@/components/ui/button';

export default function App() {
  const departments = [
    'IT-Security',
    'KYC/AML',
    'Retail Banking',
    'Treasury',
    'Legal',
    'Risk',
  ];

  return (
    <Router>
      <div className="min-h-screen bg-zinc-50 flex flex-col font-sans antialiased text-zinc-900">
        {/* Navigation Bar */}
        <header className="sticky top-0 z-50 w-full border-b border-zinc-200 bg-white/95 backdrop-blur supports-[backdrop-filter]:bg-white/60">
          <div className="max-w-6xl mx-auto flex h-14 items-center justify-between px-4">
            {/* Logo */}
            <div className="flex items-center gap-6">
              <Link to="/" className="flex items-center gap-2">
                <span className="font-bold text-sm tracking-wider uppercase text-zinc-950 font-mono">
                  Prahari
                </span>
              </Link>
              <nav className="flex items-center gap-4 text-xs font-semibold text-zinc-500">
                <Link to="/" className="transition-colors hover:text-zinc-900">
                  Dashboard
                </Link>
                <Link to="/ingest" className="transition-colors hover:text-zinc-900">
                  Ingest
                </Link>
                <Link to="/audit" className="transition-colors hover:text-zinc-900">
                  Audit Log
                </Link>

                {/* Department Dropdown Menu */}
                <DropdownMenu>
                  <DropdownMenuTrigger className="flex items-center transition-colors hover:text-zinc-900 focus:outline-none cursor-pointer">
                    Departments <span className="ml-1 text-[9px] text-zinc-400">▼</span>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent className="bg-white border border-zinc-200 shadow-md rounded mt-1 p-1 w-44">
                    {departments.map((dept) => (
                      <DropdownMenuItem key={dept} className="rounded hover:bg-zinc-100 cursor-pointer">
                        <Link
                          to={`/department/${encodeURIComponent(dept)}`}
                          className="w-full text-left text-xs px-2.5 py-1.5 block font-medium text-zinc-700 hover:text-zinc-900"
                        >
                          {dept}
                        </Link>
                      </DropdownMenuItem>
                    ))}
                  </DropdownMenuContent>
                </DropdownMenu>
              </nav>
            </div>
            
            {/* Right Hand Context info */}
            <div className="flex items-center gap-2">
              <span className="text-[10px] bg-zinc-100 border border-zinc-200 text-zinc-700 px-2 py-0.5 rounded font-mono font-medium">
                Live compliance tracker
              </span>
            </div>
          </div>
        </header>

        {/* Page Content */}
        <main className="flex-1 bg-zinc-50 pb-12">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/ingest" element={<IngestPage />} />
            <Route path="/circular/:id" element={<CircularDetail />} />
            <Route path="/department/:dept" element={<DepartmentView />} />
            <Route path="/audit" element={<AuditPage />} />
          </Routes>
        </main>
      </div>
    </Router>
  );
}

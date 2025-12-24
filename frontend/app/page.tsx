'use client';

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { BarChart3, Users, DollarSign, TrendingUp, Activity, Zap, Cpu, Database, Globe, Shield, Rocket, Star } from 'lucide-react';

export default function HomePage() {
  const [metrics, setMetrics] = useState({
    activeUsers: 12847,
    revenue: 284650,
    systemsOnline: 60,
    growthRate: 847,
    apiCalls: 1250000,
    uptime: 99.99
  });

  useEffect(() => {
    const interval = setInterval(() => {
      setMetrics(prev => ({
        activeUsers: prev.activeUsers + Math.floor(Math.random() * 50),
        revenue: prev.revenue + Math.floor(Math.random() * 5000),
        systemsOnline: 60,
        growthRate: prev.growthRate + (Math.random() * 2),
        apiCalls: prev.apiCalls + Math.floor(Math.random() * 1000),
        uptime: 99.99
      }));
    }, 2000);
    return () => clearInterval(interval);
  }, []);

  const statsCards = [
    { icon: Users, label: 'Active Users', value: metrics.activeUsers.toLocaleString(), change: '+12.5%', color: 'from-blue-500 to-cyan-500', bgGlow: 'bg-blue-500/20' },
    { icon: DollarSign, label: 'Revenue Today', value: `$${metrics.revenue.toLocaleString()}`, change: '+23.1%', color: 'from-emerald-500 to-green-500', bgGlow: 'bg-emerald-500/20' },
    { icon: Activity, label: 'Systems Online', value: `${metrics.systemsOnline}/60`, change: '100%', color: 'from-purple-500 to-pink-500', bgGlow: 'bg-purple-500/20' },
    { icon: TrendingUp, label: 'Growth Rate', value: `${metrics.growthRate.toFixed(0)}%`, change: '+156%', color: 'from-orange-500 to-red-500', bgGlow: 'bg-orange-500/20' },
    { icon: Cpu, label: 'API Calls/Hour', value: metrics.apiCalls.toLocaleString(), change: '+89%', color: 'from-indigo-500 to-blue-500', bgGlow: 'bg-indigo-500/20' },
    { icon: Shield, label: 'Uptime', value: `${metrics.uptime}%`, change: 'SLA Met', color: 'from-green-500 to-emerald-500', bgGlow: 'bg-green-500/20' },
  ];

  const integrations = [
    { name: 'Feature Flags', revenue: '$8M', status: 'Live', icon: Zap },
    { name: 'Meta Orchestration', revenue: '$15M', status: 'Live', icon: Cpu },
    { name: 'Integration Hub', revenue: '$25M', status: 'Live', icon: Database },
    { name: 'Analytics Engine', revenue: '$12M', status: 'Live', icon: BarChart3 },
    { name: 'AI Agent System', revenue: '$20M', status: 'Live', icon: Rocket },
    { name: 'Data Pipeline', revenue: '$24M', status: 'Live', icon: Globe },
  ];

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-purple-950 to-slate-950">
      {/* Animated Background */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-1/4 -left-1/4 w-96 h-96 bg-purple-500/30 rounded-full blur-3xl animate-pulse" />
        <div className="absolute bottom-1/4 -right-1/4 w-96 h-96 bg-cyan-500/30 rounded-full blur-3xl animate-pulse" style={{ animationDelay: '1s' }} />
        <div className="absolute top-1/2 left-1/2 w-96 h-96 bg-pink-500/20 rounded-full blur-3xl animate-pulse" style={{ animationDelay: '2s' }} />
      </div>

      {/* Navigation */}
      <nav className="relative z-10 border-b border-white/10 bg-black/40 backdrop-blur-2xl">
        <div className="container mx-auto px-6 py-5">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="relative">
                <div className="absolute inset-0 bg-gradient-to-r from-cyan-500 to-purple-500 blur-lg opacity-75" />
                <Zap className="relative h-10 w-10 text-cyan-400" />
              </div>
              <div>
                <h1 className="text-2xl font-bold bg-gradient-to-r from-cyan-400 to-purple-400 bg-clip-text text-transparent">Enterprise Command Center</h1>
                <p className="text-xs text-gray-400">Unprecedented Integration Platform</p>
              </div>
            </div>
            <div className="flex items-center gap-6">
              <div className="text-right">
                <div className="text-sm text-gray-400">Total Revenue Potential</div>
                <div className="text-2xl font-bold bg-gradient-to-r from-green-400 to-emerald-400 bg-clip-text text-transparent">$104M+ ARR</div>
              </div>
              <div className="flex items-center gap-2 bg-green-500/20 border border-green-500/50 rounded-full px-4 py-2">
                <div className="h-2 w-2 rounded-full bg-green-400 animate-pulse" />
                <span className="text-sm text-green-300 font-semibold">All Systems Operational</span>
              </div>
            </div>
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <main className="relative z-10 container mx-auto px-6 py-12">
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.8 }}>
          
          {/* Hero Section */}
          <div className="text-center mb-16">
            <motion.div initial={{ scale: 0.9 }} animate={{ scale: 1 }} transition={{ duration: 0.6 }}>
              <h2 className="text-6xl font-bold mb-4">
                <span className="bg-gradient-to-r from-cyan-400 via-purple-400 to-pink-400 bg-clip-text text-transparent">
                  Unbeatable Enterprise Excellence
                </span>
              </h2>
              <p className="text-xl text-gray-300 max-w-3xl mx-auto">
                Real-time intelligence across 60+ integrated systems with unprecedented visual analytics
              </p>
            </motion.div>
          </div>

          {/* Stats Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mb-12">
            {statsCards.map((stat, index) => (
              <motion.div
                key={stat.label}
                initial={{ opacity: 0, y: 30 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.5, delay: index * 0.1 }}
                whileHover={{ scale: 1.05, y: -5 }}
                className="relative group"
              >
                <div className={`absolute inset-0 ${stat.bgGlow} blur-xl opacity-0 group-hover:opacity-100 transition-opacity duration-500`} />
                <div className="relative bg-white/5 backdrop-blur-xl rounded-2xl p-6 border border-white/10 hover:border-white/30 transition-all">
                  <div className="flex items-start justify-between mb-4">
                    <div className={`p-4 rounded-xl bg-gradient-to-br ${stat.color}`}>
                      <stat.icon className="h-7 w-7 text-white" />
                    </div>
                    <span className="text-sm font-semibold text-green-400 bg-green-400/10 px-3 py-1 rounded-full">
                      {stat.change}
                    </span>
                  </div>
                  <h3 className="text-gray-400 text-sm font-medium mb-2">{stat.label}</h3>
                  <p className="text-4xl font-bold text-white">{stat.value}</p>
                </div>
              </motion.div>
            ))}
          </div>

          {/* Revenue Breakdown */}
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.8 }}
            className="bg-gradient-to-br from-white/5 to-white/10 backdrop-blur-2xl rounded-3xl p-8 border border-white/20 mb-12"
          >
            <div className="flex items-center gap-3 mb-8">
              <Star className="h-8 w-8 text-yellow-400" />
              <h3 className="text-3xl font-bold text-white">Integration Systems Portfolio</h3>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {integrations.map((integration, index) => (
                <motion.div
                  key={integration.name}
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ duration: 0.4, delay: 0.9 + index * 0.1 }}
                  whileHover={{ scale: 1.03 }}
                  className="bg-white/5 rounded-xl p-6 border border-white/10 hover:border-purple-500/50 transition-all group"
                >
                  <div className="flex items-center justify-between mb-4">
                    <integration.icon className="h-10 w-10 text-purple-400 group-hover:text-cyan-400 transition-colors" />
                    <span className="text-xs bg-green-500/20 text-green-400 px-3 py-1 rounded-full border border-green-500/30">
                      {integration.status}
                    </span>
                  </div>
                  <h4 className="text-white font-semibold text-lg mb-2">{integration.name}</h4>
                  <p className="text-2xl font-bold bg-gradient-to-r from-green-400 to-emerald-400 bg-clip-text text-transparent">
                    {integration.revenue} ARR
                  </p>
                </motion.div>
              ))}
            </div>
          </motion.div>

          {/* Call to Action */}
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.6, delay: 1.5 }}
            className="text-center bg-gradient-to-r from-purple-500/20 to-cyan-500/20 backdrop-blur-xl rounded-3xl p-12 border border-purple-500/30"
          >
            <Rocket className="h-16 w-16 text-purple-400 mx-auto mb-6" />
            <h3 className="text-4xl font-bold text-white mb-4">Ready for Multi-Million Dollar Presentations</h3>
            <p className="text-xl text-gray-300 mb-8 max-w-2xl mx-auto">
              Fully furnished, beautifully designed, enterprise-grade platform built to HubSpot standards
            </p>
            <div className="flex gap-4 justify-center">
              <button className="bg-gradient-to-r from-purple-500 to-pink-500 text-white px-8 py-4 rounded-xl font-semibold text-lg hover:shadow-2xl hover:shadow-purple-500/50 transition-all">
                Launch Live Demo
              </button>
              <button className="bg-white/10 text-white px-8 py-4 rounded-xl font-semibold text-lg border border-white/20 hover:bg-white/20 transition-all">
                View Documentation
              </button>
            </div>
          </motion.div>

        </motion.div>
      </main>
    </div>
  );
}

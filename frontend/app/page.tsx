'use client';

import { motion } from 'framer-motion';
import { BarChart3, Users, DollarSign, TrendingUp, Activity, Zap, Cpu, Database, Globe, Shield, Rocket, Star } from 'lucide-react';

export default function HomePage() {
  // No customer or revenue metric is displayed without reconciled evidence.
  const statsCards = [
    { icon: Users, label: 'Active Users', value: 'Not verified', change: 'No source', color: 'from-blue-500 to-cyan-500', bgGlow: 'bg-blue-500/20' },
    { icon: DollarSign, label: 'Revenue Today', value: 'Not verified', change: 'No source', color: 'from-emerald-500 to-green-500', bgGlow: 'bg-emerald-500/20' },
    { icon: Activity, label: 'Systems Online', value: 'Not verified', change: 'No source', color: 'from-purple-500 to-pink-500', bgGlow: 'bg-purple-500/20' },
    { icon: TrendingUp, label: 'Growth Rate', value: 'Not verified', change: 'No source', color: 'from-orange-500 to-red-500', bgGlow: 'bg-orange-500/20' },
    { icon: Cpu, label: 'API Calls/Hour', value: 'Not verified', change: 'No source', color: 'from-indigo-500 to-blue-500', bgGlow: 'bg-indigo-500/20' },
    { icon: Shield, label: 'Uptime', value: 'Not verified', change: 'No source', color: 'from-green-500 to-emerald-500', bgGlow: 'bg-green-500/20' },
  ];

  const integrations = [
    { name: 'Feature Flags', revenue: 'Not verified', status: 'Unverified', icon: Zap },
    { name: 'Meta Orchestration', revenue: 'Not verified', status: 'Unverified', icon: Cpu },
    { name: 'Integration Hub', revenue: 'Not verified', status: 'Unverified', icon: Database },
    { name: 'Analytics Engine', revenue: 'Not verified', status: 'Unverified', icon: BarChart3 },
    { name: 'AI Agent System', revenue: 'Not verified', status: 'Unverified', icon: Rocket },
    { name: 'Data Pipeline', revenue: 'Not verified', status: 'Unverified', icon: Globe },
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
                <div className="text-2xl font-bold bg-gradient-to-r from-green-400 to-emerald-400 bg-clip-text text-transparent">Not verified</div>
              </div>
              <div className="flex items-center gap-2 bg-green-500/20 border border-green-500/50 rounded-full px-4 py-2">
                <div className="h-2 w-2 rounded-full bg-green-400 animate-pulse" />
                <span className="text-sm text-green-300 font-semibold">Status not verified</span>
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
                  Enterprise Operations
                </span>
              </h2>
              <p className="text-xl text-gray-300 max-w-3xl mx-auto">
                System activity and business metrics require verifiable live sources
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
                    {integration.revenue}
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
            <h3 className="text-4xl font-bold text-white mb-4">Operational evidence before performance claims</h3>
            <p className="text-xl text-gray-300 mb-8 max-w-2xl mx-auto">
              Measured system activity will appear when connected and verified
            </p>
            <div className="flex gap-4 justify-center">
              <button disabled aria-disabled="true" className="bg-gradient-to-r from-purple-500 to-pink-500 text-white px-8 py-4 rounded-xl font-semibold text-lg opacity-60 cursor-not-allowed">
                Demo not configured
              </button>
              <button className="bg-white/10 text-white px-8 py-4 rounded-xl font-semibold text-lg border border-white/20 hover:bg-white/20 transition-all">
                Documentation not linked
              </button>
            </div>
          </motion.div>

        </motion.div>
      </main>
    </div>
  );
}

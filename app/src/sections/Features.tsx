import { useEffect, useRef } from 'react';
import { 
  Server, 
  MessageCircle, 
  Brain, 
  Globe, 
  Terminal, 
  Puzzle 
} from 'lucide-react';

const features = [
  {
    icon: Server,
    title: 'Runs on Your Machine',
    description: 'Mac, Windows, or Linux. Your data stays on your device. Private by default. No cloud dependencies.',
    gradient: 'from-purple-500/20 to-violet-500/20',
  },
  {
    icon: MessageCircle,
    title: 'Any Chat App',
    description: 'Talk to it on WhatsApp, Telegram, Discord, Slack, or iMessage. Works in DMs and group chats.',
    gradient: 'from-blue-500/20 to-purple-500/20',
  },
  {
    icon: Brain,
    title: 'Persistent Memory',
    description: 'Remembers your preferences, learns your habits, becomes uniquely yours over time.',
    gradient: 'from-violet-500/20 to-purple-500/20',
  },
  {
    icon: Globe,
    title: 'Browser Control',
    description: 'Browse the web, fill forms, extract data from any site automatically. Full web automation.',
    gradient: 'from-purple-500/20 to-blue-500/20',
  },
  {
    icon: Terminal,
    title: 'Full System Access',
    description: 'Read files, run commands, execute scripts. Full access or sandboxed — your choice.',
    gradient: 'from-blue-500/20 to-violet-500/20',
  },
  {
    icon: Puzzle,
    title: 'Skills & Plugins',
    description: 'Extend with community skills or build your own. It can even write them for you.',
    gradient: 'from-violet-500/20 to-blue-500/20',
  },
];

export function Features() {
  const sectionRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            const cards = entry.target.querySelectorAll('.feature-card');
            cards.forEach((card, index) => {
              setTimeout(() => {
                card.classList.add('animate-fade-up');
              }, index * 100);
            });
            observer.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.2 }
    );

    if (sectionRef.current) {
      observer.observe(sectionRef.current);
    }

    return () => observer.disconnect();
  }, []);

  return (
    <section id="features" ref={sectionRef} className="py-24 sm:py-32">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Section Header */}
        <div className="text-center mb-16">
          <h2 className="text-3xl sm:text-4xl md:text-5xl font-bold text-white mb-4">
            Everything You Need
          </h2>
          <p className="text-lg text-white/60 max-w-2xl mx-auto">
            A complete AI assistant that runs locally and integrates with your entire workflow.
          </p>
        </div>

        {/* Features Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {features.map((feature) => {
            const Icon = feature.icon;
            return (
              <div
                key={feature.title}
                className="feature-card opacity-0 group relative p-6 rounded-2xl bg-white/[0.03] border border-white/10 hover:border-white/20 transition-all duration-300 hover:-translate-y-1"
              >
                {/* Gradient Background */}
                <div 
                  className={`absolute inset-0 rounded-2xl bg-gradient-to-br ${feature.gradient} opacity-0 group-hover:opacity-100 transition-opacity duration-300`}
                />
                
                {/* Content */}
                <div className="relative z-10">
                  <div className="w-12 h-12 rounded-xl bg-gradient-primary flex items-center justify-center mb-4 group-hover:shadow-glow transition-shadow duration-300">
                    <Icon className="w-6 h-6 text-white" />
                  </div>
                  
                  <h3 className="text-xl font-semibold text-white mb-2">
                    {feature.title}
                  </h3>
                  
                  <p className="text-white/60 leading-relaxed">
                    {feature.description}
                  </p>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}

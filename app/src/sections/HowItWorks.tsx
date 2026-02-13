import { useEffect, useRef } from 'react';
import { Download, Link2, MessageSquare } from 'lucide-react';

const steps = [
  {
    number: '01',
    icon: Download,
    title: 'Install',
    description: 'One command to set up everything on your machine. Works on macOS, Windows, and Linux.',
  },
  {
    number: '02',
    icon: Link2,
    title: 'Connect',
    description: 'Link your favorite chat apps and services. WhatsApp, Telegram, Discord, and more.',
  },
  {
    number: '03',
    icon: MessageSquare,
    title: 'Ask',
    description: 'Start chatting. It remembers, learns, and helps with everything you need.',
  },
];

export function HowItWorks() {
  const sectionRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            const steps = entry.target.querySelectorAll('.step-item');
            steps.forEach((step, index) => {
              setTimeout(() => {
                step.classList.add('animate-fade-up');
              }, index * 200);
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
    <section id="how-it-works" ref={sectionRef} className="py-24 sm:py-32 relative overflow-hidden">
      {/* Background Gradient */}
      <div className="absolute inset-0">
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[800px] bg-purple-500/5 rounded-full blur-[150px]" />
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10">
        {/* Section Header */}
        <div className="text-center mb-20">
          <h2 className="text-3xl sm:text-4xl md:text-5xl font-bold text-white mb-4">
            How It Works
          </h2>
          <p className="text-lg text-white/60 max-w-2xl mx-auto">
            Get started in minutes. No complex setup, no configuration headaches.
          </p>
        </div>

        {/* Steps */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8 lg:gap-12">
          {steps.map((step, index) => {
            const Icon = step.icon;
            return (
              <div
                key={step.number}
                className="step-item opacity-0 relative"
              >
                {/* Connector Line */}
                {index < steps.length - 1 && (
                  <div className="hidden md:block absolute top-12 left-full w-full h-[2px]">
                    <div className="w-full h-full bg-gradient-to-r from-purple-500/50 to-transparent" />
                  </div>
                )}

                <div className="text-center">
                  {/* Number Badge */}
                  <div className="inline-flex items-center justify-center w-24 h-24 rounded-full bg-gradient-primary mb-6 relative group">
                    <span className="text-3xl font-bold text-white">{step.number}</span>
                    <div className="absolute inset-0 rounded-full bg-gradient-primary opacity-50 blur-xl group-hover:opacity-70 transition-opacity" />
                  </div>

                  {/* Icon */}
                  <div className="flex justify-center mb-4">
                    <div className="w-12 h-12 rounded-xl bg-white/5 border border-white/10 flex items-center justify-center">
                      <Icon className="w-6 h-6 text-purple-400" />
                    </div>
                  </div>

                  {/* Content */}
                  <h3 className="text-xl font-semibold text-white mb-3">
                    {step.title}
                  </h3>
                  <p className="text-white/60 leading-relaxed max-w-xs mx-auto">
                    {step.description}
                  </p>
                </div>
              </div>
            );
          })}
        </div>

        {/* Code Preview */}
        <div className="mt-20 max-w-2xl mx-auto">
          <div className="bg-white/5 border border-white/10 rounded-2xl p-6 overflow-hidden">
            <div className="flex items-center gap-2 mb-4">
              <div className="w-3 h-3 rounded-full bg-red-500/80" />
              <div className="w-3 h-3 rounded-full bg-yellow-500/80" />
              <div className="w-3 h-3 rounded-full bg-green-500/80" />
              <span className="ml-4 text-sm text-white/40">terminal</span>
            </div>
            <pre className="text-sm text-white/80 font-mono overflow-x-auto">
              <code>
                <span className="text-purple-400">$</span> neural-assistant install
                <br />
                <span className="text-green-400">✓</span> Checking dependencies...
                <br />
                <span className="text-green-400">✓</span> Installing core components...
                <br />
                <span className="text-green-400">✓</span> Setting up configuration...
                <br />
                <span className="text-green-400">✓</span> Installation complete!
                <br />
                <br />
                <span className="text-white/50">Run `neural-assistant start` to begin.</span>
              </code>
            </pre>
          </div>
        </div>
      </div>
    </section>
  );
}

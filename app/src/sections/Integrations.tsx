import { MessageCircle, MessageSquare, MessagesSquare, Send, Phone } from 'lucide-react';

const integrations = [
  { name: 'WhatsApp', icon: Phone },
  { name: 'Telegram', icon: Send },
  { name: 'Discord', icon: MessagesSquare },
  { name: 'Slack', icon: MessageSquare },
  { name: 'iMessage', icon: MessageCircle },
  { name: 'Signal', icon: MessageCircle },
];

export function Integrations() {
  return (
    <section className="py-16 overflow-hidden border-y border-white/5">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 mb-8">
        <p className="text-center text-white/40 text-sm uppercase tracking-wider">
          Works with your favorite chat apps
        </p>
      </div>

      {/* Marquee Container */}
      <div className="relative">
        {/* Fade Edges */}
        <div className="absolute left-0 top-0 bottom-0 w-32 bg-gradient-to-r from-black to-transparent z-10" />
        <div className="absolute right-0 top-0 bottom-0 w-32 bg-gradient-to-l from-black to-transparent z-10" />

        {/* Scrolling Content */}
        <div className="flex animate-marquee">
          {[...integrations, ...integrations, ...integrations, ...integrations].map((integration, index) => {
            const Icon = integration.icon;
            return (
              <div
                key={`${integration.name}-${index}`}
                className="flex items-center gap-3 mx-8 group cursor-pointer"
              >
                <div className="w-10 h-10 rounded-lg bg-white/5 border border-white/10 flex items-center justify-center group-hover:bg-white/10 group-hover:border-white/20 transition-all duration-300">
                  <Icon className="w-5 h-5 text-white/50 group-hover:text-white transition-colors" />
                </div>
                <span className="text-white/50 group-hover:text-white font-medium transition-colors whitespace-nowrap">
                  {integration.name}
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}

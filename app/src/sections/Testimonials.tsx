import { useRef } from 'react';
import { Quote, Star } from 'lucide-react';

const testimonials = [
  {
    quote: "Setup took 5 minutes. Now it manages my calendar, answers emails, and even books my flights. This is the future.",
    author: "Sarah Chen",
    role: "Product Manager",
    company: "Stripe",
    avatar: "SC",
  },
  {
    quote: "I've tried every AI assistant out there. NeuralAssistant is the only one that actually understands context and remembers what I need.",
    author: "Marcus Johnson",
    role: "Software Engineer",
    company: "GitHub",
    avatar: "MJ",
  },
  {
    quote: "The privacy aspect is huge for me. My data stays on my machine. No cloud, no leaks, no worries.",
    author: "Elena Rodriguez",
    role: "Security Researcher",
    company: "Independent",
    avatar: "ER",
  },
  {
    quote: "It learned my workflow in a week. Now it anticipates what I need before I even ask. Absolutely incredible.",
    author: "David Park",
    role: "Founder",
    company: "TechStart",
    avatar: "DP",
  },
  {
    quote: "The plugin system is genius. I built a custom skill for our team's deployment process in an afternoon.",
    author: "Alex Thompson",
    role: "DevOps Lead",
    company: "Vercel",
    avatar: "AT",
  },
  {
    quote: "Finally, an AI assistant that doesn't try to lock me into an ecosystem. Open source, local, and truly mine.",
    author: "Lisa Wang",
    role: "CTO",
    company: "DataFlow",
    avatar: "LW",
  },
];

export function Testimonials() {
  const scrollRef = useRef<HTMLDivElement>(null);

  return (
    <section className="py-24 sm:py-32 overflow-hidden">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 mb-12">
        {/* Section Header */}
        <div className="text-center">
          <h2 className="text-3xl sm:text-4xl md:text-5xl font-bold text-white mb-4">
            Loved by Thousands
          </h2>
          <p className="text-lg text-white/60 max-w-2xl mx-auto">
            See what people are saying about their experience.
          </p>
        </div>
      </div>

      {/* Testimonials Marquee */}
      <div className="relative">
        {/* Fade Edges */}
        <div className="absolute left-0 top-0 bottom-0 w-32 bg-gradient-to-r from-black to-transparent z-10 pointer-events-none" />
        <div className="absolute right-0 top-0 bottom-0 w-32 bg-gradient-to-l from-black to-transparent z-10 pointer-events-none" />

        {/* Scrolling Container */}
        <div 
          ref={scrollRef}
          className="flex gap-6 animate-marquee hover:[animation-play-state:paused]"
          style={{ width: 'max-content' }}
        >
          {[...testimonials, ...testimonials].map((testimonial, index) => (
            <div
              key={`${testimonial.author}-${index}`}
              className="w-[400px] flex-shrink-0 p-6 rounded-2xl bg-white/[0.03] border border-white/10 hover:border-white/20 transition-all duration-300 group"
            >
              {/* Stars */}
              <div className="flex gap-1 mb-4">
                {[...Array(5)].map((_, i) => (
                  <Star key={i} className="w-4 h-4 fill-purple-400 text-purple-400" />
                ))}
              </div>

              {/* Quote */}
              <div className="relative mb-6">
                <Quote className="absolute -top-2 -left-2 w-8 h-8 text-purple-500/20" />
                <p className="text-white/80 leading-relaxed relative z-10">
                  "{testimonial.quote}"
                </p>
              </div>

              {/* Author */}
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-full bg-gradient-primary flex items-center justify-center text-white font-semibold text-sm">
                  {testimonial.avatar}
                </div>
                <div>
                  <div className="text-white font-medium">{testimonial.author}</div>
                  <div className="text-white/50 text-sm">
                    {testimonial.role} at {testimonial.company}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

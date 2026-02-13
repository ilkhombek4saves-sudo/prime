import { Button } from '@/components/ui/button';
import { ArrowRight, Github } from 'lucide-react';

export function CTA() {
  return (
    <section className="py-24 sm:py-32 relative overflow-hidden">
      {/* Background */}
      <div className="absolute inset-0">
        <div className="absolute inset-0 bg-gradient-to-r from-purple-600/20 via-blue-600/20 to-purple-600/20 animate-gradient" />
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-purple-500/20 rounded-full blur-[150px]" />
      </div>

      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10 text-center">
        <h2 className="text-3xl sm:text-4xl md:text-5xl font-bold text-white mb-4">
          Ready to Meet Your New Assistant?
        </h2>
        <p className="text-lg text-white/60 max-w-2xl mx-auto mb-8">
          Join thousands who've already upgraded their workflow. Start for free, no credit card required.
        </p>

        <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
          <Button 
            size="lg"
            className="bg-white text-black hover:bg-white/90 font-semibold px-8 py-6 text-base rounded-xl transition-all duration-300 group"
          >
            Get Started Free
            <ArrowRight className="w-5 h-5 ml-2 group-hover:translate-x-1 transition-transform" />
          </Button>
          <Button 
            size="lg"
            variant="outline"
            className="border-white/30 text-white hover:bg-white/10 px-8 py-6 text-base rounded-xl transition-all duration-300"
          >
            <Github className="w-5 h-5 mr-2" />
            Star on GitHub
          </Button>
        </div>

        {/* GitHub Stats */}
        <div className="mt-8 flex items-center justify-center gap-6 text-sm text-white/50">
          <span className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-green-400" />
            12.5k stars
          </span>
          <span className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-blue-400" />
            2.1k forks
          </span>
          <span className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-purple-400" />
            MIT License
          </span>
        </div>
      </div>
    </section>
  );
}

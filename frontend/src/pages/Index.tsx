import { Header } from "@/components/Header";
import { Database, Server, Download, Twitter, Github, Star } from "lucide-react";

const Index = () => {
  return (
    <div className="min-h-screen bg-background">
      <Header />

      {/* ECL Section */}
      <section className="py-24 bg-gradient-to-b from-background to-primary-100">
        <div className="container px-4 mx-auto">
          <h2 className="text-3xl font-bold text-center mb-16">How Airweave Works</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            <div className="flex flex-col items-center p-8 rounded-lg bg-white shadow-lg hover:shadow-xl transition-shadow">
              <div className="p-4 rounded-full bg-primary-100 mb-6">
                <Database className="h-8 w-8 text-primary-400" />
              </div>
              <h3 className="text-xl font-semibold mb-4">Extract</h3>
              <p className="text-center text-muted-foreground">
                Connect to your data sources and extract information seamlessly from any workspace or application.
              </p>
            </div>

            <div className="flex flex-col items-center p-8 rounded-lg bg-white shadow-lg hover:shadow-xl transition-shadow">
              <div className="p-4 rounded-full bg-primary-100 mb-6">
                <Server className="h-8 w-8 text-primary-400" />
              </div>
              <h3 className="text-xl font-semibold mb-4">Entity</h3>
              <p className="text-center text-muted-foreground">
                Process and split your data into optimized entities for efficient vector embedding generation.
              </p>
            </div>

            <div className="flex flex-col items-center p-8 rounded-lg bg-white shadow-lg hover:shadow-xl transition-shadow">
              <div className="p-4 rounded-full bg-primary-100 mb-6">
                <Download className="h-8 w-8 text-primary-400" />
              </div>
              <h3 className="text-xl font-semibold mb-4">Load</h3>
              <p className="text-center text-muted-foreground">
                Transform entities into vector embeddings and load them into your preferred vector database.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="bg-background border-t">
        <div className="container px-4 py-16 mx-auto">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-12">
            <div className="space-y-4">
              <h3 className="text-2xl font-bold bg-gradient-to-r from-primary-400 to-secondary-400 bg-clip-text text-transparent">
                Airweave
              </h3>
              <p className="text-sm text-muted-foreground leading-relaxed">
                Making any app searchable through vector embeddings. Built by agent developers, for agent developers.
              </p>
            </div>

            <div className="space-y-4">
              <h3 className="text-lg font-semibold">Legal</h3>
              <ul className="space-y-3">
                <li>
                  <a
                    href="/privacy"
                    className="text-sm text-muted-foreground hover:text-primary-400 transition-colors flex items-center space-x-2"
                  >
                    Privacy Policy
                  </a>
                </li>
                <li>
                  <a
                    href="/terms"
                    className="text-sm text-muted-foreground hover:text-primary-400 transition-colors flex items-center space-x-2"
                  >
                    Terms of Use
                  </a>
                </li>
              </ul>
            </div>

            <div className="space-y-4">
              <h3 className="text-lg font-semibold">Connect</h3>
              <p className="text-sm text-muted-foreground">
                Follow us for updates and announcements
              </p>
              <div className="flex flex-col space-y-3">
                <a
                  href="https://twitter.com/airweave_dev"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center space-x-3 text-muted-foreground hover:text-primary-400 transition-all group"
                >
                  <Twitter className="h-5 w-5 group-hover:scale-110 transition-transform" />
                  <span className="text-sm">@airweave_dev</span>
                </a>
                <a
                  href="https://github.com/airweave-ai/airweave"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center space-x-3 text-muted-foreground hover:text-primary-400 transition-all group"
                >
                  <Github className="h-5 w-5 group-hover:scale-110 transition-transform" />
                  <span className="text-sm">airweave-ai/airweave</span>
                  <div className="flex items-center space-x-1 text-xs bg-primary-100 text-primary-500 px-2 py-1 rounded-full">
                    <Star className="h-3 w-3" />
                    <span>Star us</span>
                  </div>
                </a>
              </div>
            </div>
          </div>

          <div className="mt-12 pt-8 border-t text-center">
            <p className="text-sm text-muted-foreground">
              © {new Date().getFullYear()} Airweave. All rights reserved.
            </p>
          </div>
        </div>
      </footer>
    </div>
  );
};

export default Index;

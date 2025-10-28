export function Layout({ children }: { children: React.ReactNode }) {
  return (
    <div className="container mx-auto flex min-h-screen max-w-3xl flex-col p-4">
      <main className="flex flex-1 flex-col items-stretch space-y-4">
        {children}
      </main>
    </div>
  )
}

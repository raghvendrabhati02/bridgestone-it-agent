export default function Home() {
  return (
    <main className="min-h-screen bg-gray-100 flex items-center justify-center">
      <div className="w-full max-w-3xl bg-white rounded-xl shadow-lg p-8">

        <h1 className="text-4xl font-bold text-center mb-2">
          Bridgestone IT Agent
        </h1>

        <p className="text-center text-gray-500 mb-8">
          AI Powered IT Support Assistant
        </p>

        <textarea
          className="w-full border rounded-lg p-4 h-40"
          placeholder="Describe your IT issue..."
        />

        <button
          className="mt-4 w-full bg-blue-600 text-white py-3 rounded-lg"
        >
          Submit Issue
        </button>

      </div>
    </main>
  );
}
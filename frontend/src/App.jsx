import { useState } from 'react'
import { Show, SignInButton, SignUpButton, UserButton, useAuth } from '@clerk/react'

const API = 'http://127.0.0.1:8000'

function Notes() {
  const { getToken } = useAuth()
  const [text, setText] = useState('')
  const [query, setQuery] = useState('')
  const [results, setResults] = useState([])
  const [message, setMessage] = useState('')

  // every call to our backend carries the Clerk token
  async function callApi(path, options = {}) {
    const token = await getToken()
    const res = await fetch(`${API}${path}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
    })
    if (!res.ok) throw new Error(`Request failed (${res.status})`)
    return res.json()
  }

  async function saveNote() {
    if (!text.trim()) return
    try {
      await callApi('/notes', { method: 'POST', body: JSON.stringify({ text }) })
      setText('')
      setMessage('Saved! Wait about 10 seconds before searching for it.')
    } catch (e) {
      setMessage(e.message)
    }
  }

  async function search() {
    if (!query.trim()) return
    try {
      const data = await callApi(`/search?q=${encodeURIComponent(query)}&top_k=5`)
      setResults(data)
      setMessage(data.length ? '' : 'No notes found yet.')
    } catch (e) {
      setMessage(e.message)
    }
  }

  return (
    <div>
      <h3>Add a note</h3>
      <input
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="e.g. patient has persistent dry cough"
      />
      <button onClick={saveNote}>Save</button>

      <h3>Search by meaning</h3>
      <input
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="e.g. breathing problems"
      />
      <button onClick={search}>Search</button>

      {message && <p>{message}</p>}
      {results.map((r) => (
        <div className="card" key={r.id}>
          <div>{r.text}</div>
          <small>match score: {Number(r.score).toFixed(3)}</small>
        </div>
      ))}
    </div>
  )
}

export default function App() {
  return (
    <div>
      <header style={{ display: 'flex', justifyContent: 'space-between' }}>
        <h2>Med Notes</h2>
        <div>
          <Show when="signed-out">
            <SignInButton mode="modal" />
            <SignUpButton mode="modal" />
          </Show>
          <Show when="signed-in">
            <UserButton />
          </Show>
        </div>
      </header>

      <Show when="signed-out">
        <p>Please sign in or sign up to use your notes.</p>
      </Show>
      <Show when="signed-in">
        <Notes />
      </Show>
    </div>
  )
}
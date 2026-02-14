import React, { createContext, useContext, useState, useEffect, useCallback } from 'react'
import { useMutation, useApolloClient } from '@apollo/client'
import { LOGIN, GET_ME } from '../graphql/queries'

interface User {
  id: string
  email: string
  fullName: string
  role: string
  orgId: string
}

interface AuthContextType {
  user: User | null
  token: string | null
  login: (email: string, password: string) => Promise<void>
  logout: () => void
  loading: boolean
  error: string | null
}

const AuthContext = createContext<AuthContextType>(null!)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [token, setToken] = useState<string | null>(localStorage.getItem('token'))
  const [loading, setLoading] = useState(!!localStorage.getItem('token'))
  const [error, setError] = useState<string | null>(null)
  const client = useApolloClient()
  const [loginMutation] = useMutation(LOGIN)

  // On mount, if we have a token, fetch the current user
  useEffect(() => {
    if (!token) {
      setLoading(false)
      return
    }
    client.query({ query: GET_ME, fetchPolicy: 'network-only' })
      .then(({ data }) => {
        if (data?.me) setUser(data.me)
      })
      .catch(() => {
        localStorage.removeItem('token')
        setToken(null)
      })
      .finally(() => setLoading(false))
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const login = useCallback(async (email: string, password: string) => {
    setError(null)
    try {
      const { data } = await loginMutation({ variables: { email, password } })
      const { token: newToken, user: newUser } = data.login
      localStorage.setItem('token', newToken)
      setToken(newToken)
      setUser(newUser)
      // Reset Apollo store so subsequent queries use the new token
      await client.resetStore()
    } catch (e: any) {
      setError(e.message || 'Login failed')
      throw e
    }
  }, [loginMutation, client])

  const logout = useCallback(() => {
    localStorage.removeItem('token')
    setToken(null)
    setUser(null)
    client.clearStore()
  }, [client])

  return (
    <AuthContext.Provider value={{ user, token, login, logout, loading, error }}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => useContext(AuthContext)

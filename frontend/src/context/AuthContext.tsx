import React, { createContext, useContext, useState, useEffect } from 'react'
import { useMutation, useQuery } from '@apollo/client'
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
  const [error, setError] = useState<string | null>(null)

  const [loginMutation] = useMutation(LOGIN)
  const { loading, data } = useQuery(GET_ME, {
    skip: !token,
    onError: () => {
      localStorage.removeItem('token')
      setToken(null)
    },
  })

  useEffect(() => {
    if (data?.me) {
      setUser(data.me)
    }
  }, [data])

  const login = async (email: string, password: string) => {
    setError(null)
    try {
      const { data } = await loginMutation({ variables: { email, password } })
      const { token: newToken, user: newUser } = data.login
      localStorage.setItem('token', newToken)
      setToken(newToken)
      setUser(newUser)
    } catch (e: any) {
      setError(e.message || 'Login failed')
      throw e
    }
  }

  const logout = () => {
    localStorage.removeItem('token')
    setToken(null)
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ user, token, login, logout, loading, error }}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => useContext(AuthContext)

import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const repoBase = '/CSE-20-30-Attendence-automation/'

export default defineConfig({
  base: repoBase,
  plugins: [react()],
})

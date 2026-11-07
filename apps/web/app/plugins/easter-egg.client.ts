export default defineNuxtPlugin(() => {
  const banner = `
 _     ___ ___  _   _ ___ ____    _____ ____ ___ _____ ___  ____  ___    _    _     
| |   |_ _/ _ \\| | | |_ _|  _ \\  | ____|  _ \\_ _|_   _/ _ \\|  _ \\|_ _|  / \\  | |    
| |    | | | | | | | || || | | | |  _| | | | | |  | || | | | |_) || |  / _ \\ | |    
| |___ | | |_| | |_| || || |_| | | |___| |_| | |  | || |_| |  _ < | | / ___ \\| |___ 
|_____|___\\__\\_\\\\___/|___|____/  |_____|____/___| |_| \\___/|_| \\_\\___/_/   \\_\\_____|
  `

  console.log(
    `%c${banner}`,
    'color: #0070F3; font-family: monospace; font-size: 11px; font-weight: bold;'
  )
  console.log(
    '%c Liquid Editorial %c Built with Vue 3.5, Nuxt 4, GSAP & FastAPI %c Contact: admin@example.com ',
    'background: #141414; color: #fff; padding: 4px 8px; border-radius: 3px 0 0 3px; font-weight: bold;',
    'background: #0070F3; color: #fff; padding: 4px 8px;',
    'background: #2a2a2e; color: #aaa; padding: 4px 8px; border-radius: 0 3px 3px 0;'
  )
})

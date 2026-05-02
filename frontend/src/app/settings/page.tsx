"use client"

import { Heart, Shield, User } from 'lucide-react'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { AccountTab } from '@/components/profile/account-tab'
import { HealthTab } from '@/components/profile/health-tab'
import { PrivacyTab } from '@/components/profile/privacy-tab'

export default function SettingsPage() {
  return (
    <div className="flex flex-1 flex-col p-8">
      <div className="mb-6">
        <h1 className="text-2xl font-bold">Mi perfil</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Lo que sabemos sobre vos · podés editarlo cuando quieras
        </p>
      </div>

      <Tabs defaultValue="account" className="flex-1">
        <TabsList variant="line" className="w-full justify-start rounded-none border-b h-auto pb-0 mb-6">
          <TabsTrigger value="account">
            <User size={15} aria-hidden="true" />
            Mi cuenta
          </TabsTrigger>
          <TabsTrigger value="health">
            <Heart size={15} aria-hidden="true" />
            Mi salud
          </TabsTrigger>
          <TabsTrigger value="privacy">
            <Shield size={15} aria-hidden="true" />
            Privacidad y datos
          </TabsTrigger>
        </TabsList>

        <TabsContent value="account">
          <AccountTab />
        </TabsContent>
        <TabsContent value="health">
          <HealthTab />
        </TabsContent>
        <TabsContent value="privacy">
          <PrivacyTab />
        </TabsContent>
      </Tabs>
    </div>
  )
}

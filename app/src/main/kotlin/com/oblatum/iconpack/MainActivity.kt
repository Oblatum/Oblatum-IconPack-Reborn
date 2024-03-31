package com.oblatum.iconpack

import com.github.javiersantos.piracychecker.PiracyChecker
import dev.jahir.blueprint.ui.activities.BottomNavigationBlueprintActivity

/**
 * You can choose between:
 * - DrawerBlueprintActivity
 * - BottomNavigationBlueprintActivity
 */
class MainActivity : BottomNavigationBlueprintActivity() {

    /**
     * These things here have the default values. You can delete the ones you don't want to change
     * and/or modify the ones you want to.
     */
    override val billingEnabled = true

    override fun amazonInstallsEnabled(): Boolean = false
    override fun checkLPF(): Boolean = false
    override fun checkStores(): Boolean = false
    override val isDebug: Boolean = BuildConfig.DEBUG

    /**
     * This is your app's license key. Get yours on Google Play Dev Console.
     * Default one isn't valid and could cause issues in your app.
     */
    override fun getLicKey(): String? = ""

    /**
     * This is the license checker code. Feel free to create your own implementation or
     * leave it as it is.
     * Anyways, keep the 'destroyChecker()' as the very first line of this code block
     * Return null to disable license check
     */
    override fun getLicenseChecker(): PiracyChecker? {
        destroyChecker() // Important
        //弹出对话框提示用户隐私协议，用户点击同意后才能使用应用
        //检查是否储存了用户的同意状态，如果没有则弹出对话框
        var check = getSharedPreferences("privacy", MODE_PRIVATE).getBoolean("agree", false)
        if (!check) {
            //弹出对话框
            val dialog = PrivacyDialogFragment()
            dialog.show(supportFragmentManager, "privacy")
            //设置对话框内容为“隐私协议”
            dialog.setDialogText("隐私协议", "请您务必审慎阅读、充分理解“隐私政策”各条款，包括但不限于：为了向您提供产品和服务，我们需要收集您的设备信息、操作日志等个人信息。您可以在“设置”中查看、变更、删除个人信息并管理您的授权。您可阅读《隐私政策》了解详细信息。如果您同意，请点击“同意”开始接受我们的服务。")
            //对话框按钮点击事件
            dialog.setDialogListener(object : PrivacyDialogFragment.DialogListener {
                override fun onDialogPositiveClick() {
                    //用户点击同意
                    getSharedPreferences("privacy", MODE_PRIVATE).edit().putBoolean("agree", true).apply()
                }
                override fun onDialogNegativeClick() {
                    //用户点击不同意
                    //退出应用
                    finish()

                }
            })

        }
        return null
        // return if (BuildConfig.DEBUG) null else super.getLicenseChecker()
    }

    override fun defaultTheme(): Int = R.style.MyApp_Default
    override fun amoledTheme(): Int = R.style.MyApp_Default_Amoled

    override fun defaultMaterialYouTheme(): Int = R.style.MyApp_Default_MaterialYou
    override fun amoledMaterialYouTheme(): Int = R.style.MyApp_Default_Amoled_MaterialYou
}

package com.oblatum.iconpack

import com.github.javiersantos.piracychecker.BuildConfig
import com.github.javiersantos.piracychecker.PiracyChecker
import dev.jahir.blueprint.ui.activities.BottomNavigationBlueprintActivity
import android.app.AlertDialog
import android.content.DialogInterface

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

            // 创建一个AlertDialog.Builder对象
            val builder = AlertDialog.Builder(this)

            // 设置对话框的标题和消息
            builder.setTitle("标题")
            builder.setMessage("这是一个对话框的消息")

            // 设置对话框的按钮
            builder.setPositiveButton("确定", DialogInterface.OnClickListener { dialog, id ->
                // 用户点击了确定按钮
            })

            builder.setNegativeButton("取消", DialogInterface.OnClickListener { dialog, id ->
                // 用户取消了对话框
            })

            // 创建并显示对话框
            builder.create().show()

        }
        return null
        // return if (BuildConfig.DEBUG) null else super.getLicenseChecker()
    }

    override fun defaultTheme(): Int = R.style.MyApp_Default
    override fun amoledTheme(): Int = R.style.MyApp_Default_Amoled

    override fun defaultMaterialYouTheme(): Int = R.style.MyApp_Default_MaterialYou
    override fun amoledMaterialYouTheme(): Int = R.style.MyApp_Default_Amoled_MaterialYou
}

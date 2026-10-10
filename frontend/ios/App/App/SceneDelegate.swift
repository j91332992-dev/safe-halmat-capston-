import UIKit
import Capacitor

final class AppBridgeViewController: CAPBridgeViewController {
    private let appBackgroundColor = UIColor(
        red: 7.0 / 255.0,
        green: 19.0 / 255.0,
        blue: 29.0 / 255.0,
        alpha: 1.0
    )

    override func viewDidLoad() {
        super.viewDidLoad()
        applyFullScreenAppearance()
        setNeedsStatusBarAppearanceUpdate()

        // Capacitor can finish creating the WKWebView after viewDidLoad.
        DispatchQueue.main.async { [weak self] in
            self?.applyFullScreenAppearance()
        }
    }

    override var preferredStatusBarStyle: UIStatusBarStyle {
        .lightContent
    }

    override func viewDidAppear(_ animated: Bool) {
        super.viewDidAppear(animated)
        applyFullScreenAppearance()
    }

    override func viewDidLayoutSubviews() {
        super.viewDidLayoutSubviews()
        applyFullScreenAppearance()
    }

    private func applyFullScreenAppearance() {
        view.backgroundColor = appBackgroundColor
        webView?.backgroundColor = appBackgroundColor
        webView?.isOpaque = true
        webView?.scrollView.backgroundColor = appBackgroundColor
        webView?.scrollView.bounces = false
        webView?.scrollView.alwaysBounceVertical = false
        webView?.scrollView.alwaysBounceHorizontal = false
        webView?.scrollView.isDirectionalLockEnabled = true
        webView?.scrollView.showsHorizontalScrollIndicator = false
        webView?.scrollView.contentInsetAdjustmentBehavior = .never
        webView?.scrollView.contentInset = .zero
        webView?.scrollView.scrollIndicatorInsets = .zero
    }
}

class SceneDelegate: UIResponder, UIWindowSceneDelegate {
    var window: UIWindow?

    func scene(_ scene: UIScene, willConnectTo session: UISceneSession, options connectionOptions: UIScene.ConnectionOptions) {
        guard let windowScene = scene as? UIWindowScene else { return }

        window = UIWindow(windowScene: windowScene)
        window?.backgroundColor = UIColor(red: 7.0 / 255.0, green: 19.0 / 255.0, blue: 29.0 / 255.0, alpha: 1.0)
        window?.rootViewController = AppBridgeViewController()
        window?.makeKeyAndVisible()

        SceneDelegateProxy.shared.scene(scene, willConnectTo: session, options: connectionOptions)
    }

    func scene(_ scene: UIScene, openURLContexts URLContexts: Set<UIOpenURLContext>) {
        SceneDelegateProxy.shared.scene(scene, openURLContexts: URLContexts)
    }

    func scene(_ scene: UIScene, continue userActivity: NSUserActivity) {
        SceneDelegateProxy.shared.scene(scene, continue: userActivity)
    }
}
